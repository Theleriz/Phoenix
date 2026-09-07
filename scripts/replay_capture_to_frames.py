"""Replay a real WT901BLE68 capture through the transport preprocessing stage
and export a model-ready ``(T, 3, 9)`` array.

Non-clinical development tool. It exists so the ML side can build
``build_model_input()`` against genuine hardware data without standing up the
API, the database or Docker. It calculates no ROM, repetitions, score or
clinical feedback.

Input : one ``services/imu-gateway/captures/*.jsonl`` file (records tagged
        ``origin: "hardware"``, ``validation_status: "unverified_checksum"``).
Output: written next to ``--out`` (default ``scripts/out/``):
  <name>.frames.json      full preprocess_transport_events() output, RAW units
                          (accel/gyro int16 LSB, orientation degrees)
  <name>.model_input.npy  float32 (T, 3, 9), PHYSICAL units (see below)
  <name>.meta.json        channel/sensor order, unit conversions, per-frame
                          quality flags, and the real signal-quality verdict
  <name>.windows.npy      float32 (N, W, 3, 9) sliding windows, if --window given

Channel axis order (index 2), matches preprocessing.CHANNELS:
  ax ay az  gx gy gz  ori_roll ori_pitch ori_yaw
Sensor axis order (index 1), matches preprocessing.REQUIRED_ROLES:
  thigh shank foot

Unit conversion applied to model_input.npy / windows.npy ONLY (frames.json
stays raw). Scales are datasheet values for the WT901BLE68; see the status
field in meta.json:
  accel : LSB * (16 / 32768)   -> g       (VERIFIED: rest |a| ~ 2048 LSB ~ 1 g)
  gyro  : LSB * (2000 / 32768) -> deg/s   (ASSUMED: not bench-verified)
  orient: degrees, unchanged
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "biomechanics"))
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "app"))

from preprocessing import CHANNELS, REQUIRED_ROLES, preprocess_transport_events  # noqa: E402

try:
    from signal_quality import evaluate_signal_quality  # noqa: E402

    _HAVE_SIGNAL_QUALITY = True
except Exception:  # pragma: no cover - optional, import path only
    _HAVE_SIGNAL_QUALITY = False

DEFAULT_CAPTURE_DIR = REPO_ROOT / "services" / "imu-gateway" / "captures"

ACCEL_CHANNELS = ("ax", "ay", "az")
GYRO_CHANNELS = ("gx", "gy", "gz")
ORIENTATION_CHANNELS = ("ori_roll", "ori_pitch", "ori_yaw")

# Datasheet full-scale over int16. See module docstring for verification status.
ACCEL_G_PER_LSB = 16.0 / 32768.0
GYRO_DPS_PER_LSB = 2000.0 / 32768.0


def resolve_capture(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_file():
        return candidate
    named = DEFAULT_CAPTURE_DIR / value
    if named.is_file():
        return named
    named_jsonl = DEFAULT_CAPTURE_DIR / f"{value}.jsonl"
    if named_jsonl.is_file():
        return named_jsonl
    raise SystemExit(f"capture not found: {value}")


def capture_row_to_event(row: dict[str, Any]) -> dict[str, Any] | None:
    """Map one capture JSONL record to the gateway-event shape preprocessing
    expects. Returns None if the row is missing a field the pipeline needs."""
    sensor = row.get("sensor") or {}
    role = sensor.get("role")
    accel = row.get("accelerometer_raw")
    gyro = row.get("gyroscope_raw")
    euler = row.get("euler_degrees")
    ts = row.get("gateway_timestamp")
    if role not in REQUIRED_ROLES or ts is None:
        return None
    if not isinstance(accel, list) or not isinstance(gyro, list):
        return None
    if len(accel) != 3 or len(gyro) != 3:
        return None
    event: dict[str, Any] = {
        "sensor_role": role,
        "timestamp_gateway": ts,
        "ax": accel[0], "ay": accel[1], "az": accel[2],
        "gx": gyro[0], "gy": gyro[1], "gz": gyro[2],
        "sequence_number": row.get("sequence_number"),
        "origin": row.get("origin", "hardware"),
    }
    if isinstance(euler, list) and len(euler) == 3:
        event["orientation_euler_degrees"] = euler
    return event


def load_events(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    events: list[dict[str, Any]] = []
    per_role: dict[str, int] = {role: 0 for role in REQUIRED_ROLES}
    skipped = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            event = capture_row_to_event(json.loads(line))
            if event is None:
                skipped += 1
                continue
            events.append(event)
            per_role[event["sensor_role"]] += 1
    per_role["_skipped_rows"] = skipped
    return events, per_role


def frames_to_physical_array(frames: list[dict[str, Any]]) -> np.ndarray:
    """(T, 3, 9) float32 in g / deg-per-s / degrees."""
    tensor = np.zeros((len(frames), len(REQUIRED_ROLES), len(CHANNELS)), dtype=np.float32)
    for t_index, frame in enumerate(frames):
        for s_index, role in enumerate(REQUIRED_ROLES):
            sensor = frame["sensors"][role]
            for c_index, channel in enumerate(CHANNELS):
                value = sensor[channel]
                if channel in ACCEL_CHANNELS:
                    value *= ACCEL_G_PER_LSB
                elif channel in GYRO_CHANNELS:
                    value *= GYRO_DPS_PER_LSB
                tensor[t_index, s_index, c_index] = value
    return tensor


def sliding_windows(tensor: np.ndarray, window: int, stride: int) -> np.ndarray:
    if window <= 0 or stride <= 0:
        raise SystemExit("--window and --stride must be positive")
    if tensor.shape[0] < window:
        return np.empty((0, window, tensor.shape[1], tensor.shape[2]), dtype=tensor.dtype)
    starts = range(0, tensor.shape[0] - window + 1, stride)
    return np.stack([tensor[start : start + window] for start in starts]).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "capture", help="path to a capture .jsonl, or its bare name in the captures/ dir"
    )
    parser.add_argument(
        "--out", default=str(REPO_ROOT / "scripts" / "out"), help="output directory"
    )
    parser.add_argument(
        "--rate", type=float, default=20.0, help="target resample rate Hz (default 20)"
    )
    parser.add_argument(
        "--filter-window",
        type=int,
        default=1,
        help="centered moving-average width, odd; 1 = no smoothing (the default)",
    )
    parser.add_argument(
        "--window", type=int, default=0, help="if >0, also emit sliding windows of this length"
    )
    parser.add_argument(
        "--stride", type=int, default=0, help="sliding-window stride (default: window // 2)"
    )
    args = parser.parse_args()

    capture_path = resolve_capture(args.capture)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = capture_path.stem
    source_sha = hashlib.sha256(capture_path.read_bytes()).hexdigest()

    events, per_role = load_events(capture_path)
    signal_quality_report: dict[str, Any] | None = None
    if _HAVE_SIGNAL_QUALITY:
        try:
            signal_quality_report = evaluate_signal_quality(events).as_dict()
        except Exception as error:  # pragma: no cover - diagnostic only
            signal_quality_report = {"error": repr(error)}

    # Force the gate open: this is a dev tool operating on already-captured real
    # data. The real verdict above tells you whether production would have run
    # preprocessing at all.
    result = preprocess_transport_events(
        events,
        signal_quality={"scoring_permitted": True},
        target_rate_hz=args.rate,
        filter_window_samples=args.filter_window,
    )

    frames_payload = {
        "allowed": result.allowed,
        "reasons": list(result.reasons),
        "sample_rate_hz": result.sample_rate_hz,
        "parameters": result.parameters,
        "frames": list(result.frames),
    }
    frames_file = out_dir / f"{name}.frames.json"
    frames_file.write_text(json.dumps(frames_payload, indent=2), encoding="utf-8")

    meta: dict[str, Any] = {
        "source_file": str(capture_path.relative_to(REPO_ROOT)),
        "source_sha256": source_sha,
        "events_total": len(events),
        "events_per_role": per_role,
        "target_rate_hz": args.rate,
        "filter_window_samples": args.filter_window,
        "channel_order": list(CHANNELS),
        "sensor_order": list(REQUIRED_ROLES),
        "model_input_units": {
            "ax_ay_az": {"unit": "g", "lsb_scale": ACCEL_G_PER_LSB, "status": "verified"},
            "gx_gy_gz": {"unit": "deg/s", "lsb_scale": GYRO_DPS_PER_LSB, "status": "assumed"},
            "ori_roll_ori_pitch_ori_yaw": {
                "unit": "degrees",
                "lsb_scale": 1.0,
                "status": "device_reported",
            },
        },
        "allowed": result.allowed,
        "reasons": list(result.reasons),
        "real_signal_quality": signal_quality_report,
    }

    if not result.allowed:
        meta["model_input"] = None
        (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"preprocessing rejected this capture: {', '.join(result.reasons) or 'unknown'}")
        print(f"  wrote {frames_file}")
        print(f"  wrote {out_dir / (name + '.meta.json')}")
        return

    frames = list(result.frames)
    tensor = frames_to_physical_array(frames)
    model_input_file = out_dir / f"{name}.model_input.npy"
    np.save(model_input_file, tensor)

    gap_frames = [i for i, f in enumerate(frames) if f["flags"]["interpolated_over_gap"]]
    clip_frames = [i for i, f in enumerate(frames) if f["flags"]["near_full_scale"]]
    duration_s = (
        frames[-1]["timestamp_gateway"] - frames[0]["timestamp_gateway"] if frames else 0.0
    )
    meta["model_input"] = {
        "file": model_input_file.name,
        "shape": list(tensor.shape),
        "dtype": "float32",
        "duration_seconds": round(duration_s, 3),
        "frames_total": len(frames),
        "frames_interpolated_over_gap": gap_frames,
        "frames_near_full_scale": clip_frames,
    }

    if args.window > 0:
        stride = args.stride or max(1, args.window // 2)
        windows = sliding_windows(tensor, args.window, stride)
        windows_file = out_dir / f"{name}.windows.npy"
        np.save(windows_file, windows)
        window_flags = []
        for w_index in range(windows.shape[0]):
            start = w_index * stride
            span = range(start, start + args.window)
            window_flags.append(
                {
                    "index": w_index,
                    "start_frame": start,
                    "has_gap_frame": any(i in gap_frames for i in span),
                    "has_clip_frame": any(i in clip_frames for i in span),
                }
            )
        meta["windows"] = {
            "file": windows_file.name,
            "shape": list(windows.shape),
            "window_samples": args.window,
            "stride_samples": stride,
            "clean_windows": sum(
                1 for wf in window_flags if not wf["has_gap_frame"] and not wf["has_clip_frame"]
            ),
            "flags": window_flags,
        }

    (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    per_role_summary = ", ".join(f"{role}: {per_role[role]}" for role in REQUIRED_ROLES)
    print(f"capture         {capture_path.relative_to(REPO_ROOT)}")
    print(f"events          {len(events)}  per role {{{per_role_summary}}}")
    if signal_quality_report and "level" in signal_quality_report:
        print(
            f"real signal q.  {signal_quality_report['level']}  "
            f"scoring_permitted={signal_quality_report.get('scoring_permitted')}  "
            f"rates={signal_quality_report.get('sample_rates_hz')}"
        )
    print(f"frames          {len(frames)} @ {args.rate} Hz  ({round(duration_s, 2)} s)")
    print(f"  gap-bridged   {len(gap_frames)}")
    print(f"  near-full-sc. {len(clip_frames)}")
    print(f"model_input     {tuple(tensor.shape)} float32  -> {model_input_file}")
    if args.window > 0:
        print(f"windows         {tuple(windows.shape)} float32  -> {windows_file}")
    print(f"frames.json     {frames_file}")
    print(f"meta.json       {out_dir / (name + '.meta.json')}")


if __name__ == "__main__":
    main()
