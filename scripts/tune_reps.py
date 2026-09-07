"""Offline tuner for the deterministic rep counter.

Record a known number of real repetitions, then run this against that data to
see which sensor pair / orientation axis carries the movement and how many
reps each threshold set detects. Use the result to edit
``services/api/app/reps.py``.

Data source (one of):
  --session <rehab_session_id>   pull packets from the running compose postgres
  --file <path.jsonl>            a capture JSONL (either the gateway-event shape
                                 or services/imu-gateway/captures/*.jsonl shape)

Examples:
  python scripts/tune_reps.py --session <id> --expected 10
  python scripts/tune_reps.py --file dump.jsonl --expected 8 --enter 15 --exit 6
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from app.preprocessing import preprocess_transport_events  # noqa: E402

ROLES = ("thigh", "shank", "foot")
AXES = ("ori_roll", "ori_pitch", "ori_yaw")
AXIS_SHORT = {"ori_roll": "roll", "ori_pitch": "pitch", "ori_yaw": "yaw"}


def load_events(args: argparse.Namespace) -> list[dict]:
    if args.session:
        from replay_capture_to_api import psql

        out = psql(
            "SELECT payload FROM gateway_packet_events "
            f"WHERE rehab_session_id = '{args.session}' ORDER BY received_at, id;"
        )
        rows = [json.loads(line) for line in out.splitlines() if line.strip()]
    else:
        rows = [
            json.loads(line)
            for line in Path(args.file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return [normalise(row) for row in rows if normalise(row) is not None]


def normalise(row: dict) -> dict | None:
    """Accept both the gateway-event shape and the capture-file shape."""
    if "sensor_role" in row and "orientation_euler_degrees" in row:
        role = row["sensor_role"]
        euler = row["orientation_euler_degrees"]
        ts = row["timestamp_gateway"]
        accel = (row.get("ax", 0), row.get("ay", 0), row.get("az", 0))
        gyro = (row.get("gx", 0), row.get("gy", 0), row.get("gz", 0))
    elif "sensor" in row and "euler_degrees" in row:
        role = row["sensor"]["role"]
        euler = row["euler_degrees"]
        ts = row["gateway_timestamp"]
        accel = row.get("accelerometer_raw", (0, 0, 0))
        gyro = row.get("gyroscope_raw", (0, 0, 0))
    else:
        return None
    if role not in ROLES or not isinstance(euler, list | tuple) or len(euler) != 3:
        return None
    return {
        "sensor_role": role,
        "timestamp_gateway": ts,
        "ax": int(accel[0]), "ay": int(accel[1]), "az": int(accel[2]),
        "gx": int(gyro[0]), "gy": int(gyro[1]), "gz": int(gyro[2]),
        "orientation_euler_degrees": [float(euler[0]), float(euler[1]), float(euler[2])],
    }


def _wrap(degrees: float) -> float:
    """Map an angle difference into (-180, 180] so the +/-180 wrap does not
    create fake jumps in the flexion signal."""
    return ((degrees + 180.0) % 360.0) - 180.0


def count_cycles(magnitude: list[float], enter: float, exit_: float, min_frames: int) -> int:
    """Same hysteresis state machine as reps.count_repetitions."""
    count = 0
    state = "rest"
    start = 0
    peak = 0.0
    for index, value in enumerate(magnitude):
        if state == "rest":
            if value >= enter:
                state, start, peak = "flexed", index, value
        else:
            peak = max(peak, value)
            if value <= exit_:
                if index - start >= min_frames and peak >= enter:
                    count += 1
                state = "rest"
    return count


def oriented_magnitude(signal: list[float]) -> tuple[list[float], float]:
    baseline = statistics.median(signal)
    sign = 1.0 if (max(signal) - baseline) >= (baseline - min(signal)) else -1.0
    magnitude = [sign * (value - baseline) for value in signal]
    return magnitude, max(magnitude)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--session", help="rehab_session_id in the running DB")
    src.add_argument("--file", help="path to a JSONL dump")
    parser.add_argument("--expected", type=int, default=None, help="reps you actually did")
    parser.add_argument("--rate", type=float, default=20.0)
    parser.add_argument("--enter", type=float, default=18.0)
    parser.add_argument("--exit", dest="exit_", type=float, default=7.0)
    parser.add_argument("--min-frames", type=int, default=5)
    parser.add_argument("--dump-csv", help="write the best candidate signal to this CSV")
    args = parser.parse_args()

    events = load_events(args)
    per_role = {r: sum(1 for e in events if e["sensor_role"] == r) for r in ROLES}
    print(f"events: {len(events)}  per role: {per_role}")
    if min(per_role.values()) == 0:
        raise SystemExit("missing a sensor stream -- cannot analyse")

    result = preprocess_transport_events(
        events, signal_quality={"scoring_permitted": True},
        target_rate_hz=args.rate, filter_window_samples=1,
    )
    if not result.allowed:
        raise SystemExit(f"preprocessing rejected: {', '.join(result.reasons)}")
    frames = list(result.frames)
    print(f"frames: {len(frames)} @ {args.rate} Hz  ({round(len(frames) / args.rate, 1)} s)\n")

    pairs = (("shank", "thigh"), ("shank", "foot"), ("thigh", "foot"))
    candidates: list[tuple[str, list[float], float, int]] = []
    for distal, proximal in pairs:
        for axis in AXES:
            signal = [
                _wrap(float(f["sensors"][distal][axis]) - float(f["sensors"][proximal][axis]))
                for f in frames
            ]
            magnitude, amplitude = oriented_magnitude(signal)
            detected = count_cycles(magnitude, args.enter, args.exit_, args.min_frames)
            name = f"{distal}-{proximal} {AXIS_SHORT[axis]}"
            candidates.append((name, magnitude, amplitude, detected))

    header = f"{'candidate':<20} {'amplitude':>10} {'reps':>6}"
    if args.expected is not None:
        header += f"  {'err':>5}"
    print(header)
    print("-" * len(header))
    candidates.sort(key=lambda c: c[2], reverse=True)
    for name, _magnitude, amplitude, detected in candidates:
        line = f"{name:<20} {amplitude:>9.1f}° {detected:>6}"
        if args.expected is not None:
            line += f"  {detected - args.expected:>+5}"
        print(line)

    best = candidates[0]
    if args.expected is not None:
        exact = [c for c in candidates if c[3] == args.expected and c[2] >= args.enter]
        if exact:
            best = max(exact, key=lambda c: c[2])
    print(f"\nbest candidate: {best[0]}  (amplitude {best[2]:.1f}°, {best[3]} reps)")
    print(
        "current reps.py uses: shank-thigh pitch, enter=18, exit=7. "
        "If the best row above differs, that is the change to make."
    )

    if args.dump_csv:
        rows = ["frame,magnitude_deg"]
        rows += [f"{i},{v:.3f}" for i, v in enumerate(best[1])]
        Path(args.dump_csv).write_text("\n".join(rows), encoding="utf-8")
        print(f"wrote {args.dump_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
