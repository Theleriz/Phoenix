"""Continuously feed the live API so the patient rep counter keeps moving.

Development-only. Two sources:

* default -- replays a real ``services/imu-gateway/captures/*.jsonl`` file,
  looping forever, rebasing every packet's ``timestamp_gateway`` onto the wall
  clock so the recent-window rep detector keeps producing fresh completions.
* ``--synthetic`` -- generates clean heel-slide flexion/extension cycles at a
  fixed cadence (``--rep-seconds``); the crispest way to watch the counter tick.

One stable session id, monotonically increasing sequence numbers (no 409s).
Each ingest runs the real pipeline
(signal_quality -> preprocess -> shadow ML -> deterministic rep count); this
script prints every ``just_completed`` rep edge.

Point the patient app at the same session to watch the counter:

    http://localhost:8080/?stream=<session-id>

Prereqs: stack up (``docker compose ... up -d postgres api``) and, for the real
capture, ``PHOENIX_ML_FORCE_INFERENCE=1`` in ``.env`` (already set) so the branch
runs on its LOW signal quality.

Usage from the repo root:

    python scripts/stream_capture_loop.py --synthetic
    python scripts/stream_capture_loop.py --capture capture-02.jsonl
    python scripts/stream_capture_loop.py --synthetic --rep-seconds 2.5 --session-id demo
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import UTC, datetime, timedelta

from replay_capture_to_api import (
    ADAPTER_VERSION,
    DEFAULT_API_URL,
    DEFAULT_TOKEN,
    DOTENV,
    ROLES,
    post_packet,
    psql,
    resolve_capture,
    seed_hardware_session,
)

RATE_HZ = 20.0


def starting_sequences(session_id: str) -> dict[str, int]:
    """Continue past any packets this session already has, so re-running the
    loop on the same --session-id does not 409 on every packet."""
    seqs = {role: 0 for role in ROLES}
    try:
        out = psql(
            "SELECT sensor_role, MAX(sequence_number) + 1 "
            f"FROM gateway_packet_events WHERE rehab_session_id = '{session_id}' "
            "GROUP BY sensor_role;",
            quiet=True,
        )
    except SystemExit:
        return seqs
    for line in out.splitlines():
        if "|" in line:
            role, value = line.split("|", 1)
            if role.strip() in seqs and value.strip():
                seqs[role.strip()] = int(value)
    return seqs


def _packet(session_id: str, role: str, seq: int, moment: datetime, accel, gyro, euler):
    return {
        "session_id": session_id,
        "device_id": f"hw-{role}",
        "sensor_role": role,
        "timestamp_device": None,
        "timestamp_gateway": moment.isoformat(),
        "sequence_number": seq,
        "ax": int(accel[0]), "ay": int(accel[1]), "az": int(accel[2]),
        "gx": int(gyro[0]), "gy": int(gyro[1]), "gz": int(gyro[2]),
        "orientation_euler_degrees": [float(euler[0]), float(euler[1]), float(euler[2])],
        "battery": None,
        "origin": "hardware",
        "validation_status": "unverified_checksum",
        "adapter_version": ADAPTER_VERSION,
    }


def _synthetic_frames(rep_seconds: float):
    """Yield (role, accel, gyro, euler) tuples for one flexion/extension cycle.

    The rep detector's proxy is shank.ori_pitch - thigh.ori_pitch, so only the
    shank pitch is driven: 0 -> ~45 deg -> 0 over `rep_seconds`.
    """
    samples = max(4, round(rep_seconds * RATE_HZ))
    for i in range(samples):
        flex = 45.0 * (0.5 - 0.5 * math.cos(2 * math.pi * i / samples))
        yield "thigh", (0, 0, 2048), (0, 0, 0), (0.0, 0.0, 0.0)
        yield "shank", (0, 0, 2048), (0, 0, 0), (0.0, flex, 0.0)
        yield "foot", (0, 0, 2048), (0, 0, 0), (0.0, flex / 3.0, 0.0)


def _capture_frames(path):
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for record in records:
        role = str(record["sensor"]["role"])
        if role in ROLES:
            yield (
                role,
                record["accelerometer_raw"],
                record["gyroscope_raw"],
                record["euler_degrees"],
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--capture", default="capture-01.jsonl")
    parser.add_argument("--synthetic", action="store_true", help="generate clean reps instead")
    parser.add_argument("--rep-seconds", type=float, default=3.0, help="synthetic: seconds per rep")
    parser.add_argument("--session-id", default="live-stream")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--token", default=DOTENV.get("PHOENIX_GATEWAY_TOKEN", DEFAULT_TOKEN))
    parser.add_argument("--sleep", type=float, default=1.0 / RATE_HZ / 3)
    parser.add_argument("--no-db", action="store_true", help="skip DB seeding")
    args = parser.parse_args()

    session_id = args.session_id
    attempt_id = f"{session_id}-attempt"
    if not args.no_db:
        print(f"seeding hardware session {session_id} ...")
        seed_hardware_session(session_id, attempt_id)

    sequences = starting_sequences(session_id)
    if any(sequences.values()):
        print(f"continuing sequence numbers from {sequences}")

    if args.synthetic:
        frames = list(_synthetic_frames(args.rep_seconds))
        label = f"synthetic reps ({args.rep_seconds}s each)"
    else:
        capture = resolve_capture(args.capture)
        frames = list(_capture_frames(capture))
        label = capture.name

    print(f"streaming {label} -> {args.api_url}  session={session_id}")
    print(f"watch:  {args.api_url.replace('8000', '8080')}/?stream={session_id}\n")

    step = timedelta(seconds=1.0 / RATE_HZ)
    moment = datetime.now(UTC)
    reps_seen = 0
    last_rep_at: float | None = None
    try:
        while True:
            for role, accel, gyro, euler in frames:
                packet = _packet(session_id, role, sequences[role], moment, accel, gyro, euler)
                sequences[role] += 1
                if role == ROLES[-1]:
                    moment += step
                status, payload = post_packet(args.api_url, args.token, packet)
                if status not in (200, 202):
                    continue
                rep = (payload or {}).get("repetitions") or {}
                completed_at = rep.get("last_completed_at")
                if completed_at is not None and (last_rep_at is None or completed_at > last_rep_at):
                    first = last_rep_at is None
                    last_rep_at = completed_at
                    if first:
                        continue
                    reps_seen += 1
                    print(
                        f"  rep #{reps_seen}  window_count={rep.get('window_count')} "
                        f"target={rep.get('target')} amp={rep.get('amplitude_degrees')}deg"
                    )
                if args.sleep:
                    time.sleep(args.sleep)
    except KeyboardInterrupt:
        print(f"\nstopped after {reps_seen} reps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
