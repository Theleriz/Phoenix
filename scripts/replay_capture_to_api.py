"""Replay a real WT901BLE68 capture through the live API gateway endpoint.

Development-only end-to-end check for the Stage 9 ML shadow path. It takes a
genuine hardware capture (``services/imu-gateway/captures/*.jsonl``, records
tagged ``origin: "hardware"`` / ``validation_status: "unverified_checksum"``)
and POSTs every sample to ``/api/v1/gateway/imu-packets`` exactly as the
patient web app's Web Bluetooth client would, so the API runs its real
pipeline on real data:

    raw store -> evaluate_signal_quality -> preprocess_transport_events
              -> ml.run_shadow_inference -> shadow_predictions

It calculates no ROM, repetitions, score or clinical feedback and it never
makes anything patient-visible -- shadow predictions stay shadow-mode.

Prerequisites (the choices already agreed):
  * stack up via docker compose:
        docker compose -f infra/docker-compose.yml up -d postgres api
  * PHOENIX_ML_FORCE_INFERENCE=1 in .env (already set) -- the real captures
    have no stay-still calibration hold so signal quality is LOW; without the
    override the API would (correctly, for production) skip the ML branch.

Usage from the repo root:

    python scripts/replay_capture_to_api.py                 # capture-01.jsonl
    python scripts/replay_capture_to_api.py --capture capture-02.jsonl
    python scripts/replay_capture_to_api.py --all --sleep 0.01
    python scripts/replay_capture_to_api.py --session-id my-run-2   # re-run clean

The gateway_packet_events table is append-only (immutable trigger), so a
second run with the same ``--session-id`` gets 409s on every packet. Pass a
fresh ``--session-id`` to replay from scratch.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE_DIR = REPO_ROOT / "services" / "imu-gateway" / "captures"
COMPOSE_FILE = REPO_ROOT / "infra" / "docker-compose.yml"

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_TOKEN = "change-me-local-only-gateway-token"
ORG_ID = "org-demo"
EPISODE_ID = "episode-demo"
PRESCRIPTION_ID = "prescription-heel-slide-demo-v1"
ROLES = ("thigh", "shank", "foot")
ADAPTER_VERSION = "phoenix-replay-capture-0.1.0"


def _env_from_dotenv() -> dict[str, str]:
    env: dict[str, str] = {}
    dotenv = REPO_ROOT / ".env"
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


DOTENV = _env_from_dotenv()
PG_USER = DOTENV.get("POSTGRES_USER", "phoenix_dev")
PG_DB = DOTENV.get("POSTGRES_DB", "phoenix")


# --- docker compose exec -> psql -----------------------------------------------


def _compose_cmd() -> list[str]:
    for candidate in (["docker", "compose"], ["docker-compose"]):
        try:
            subprocess.run(
                [*candidate, "version"],
                capture_output=True,
                check=True,
            )
            return candidate
        except (OSError, subprocess.CalledProcessError):
            continue
    raise SystemExit(
        "Neither `docker compose` nor `docker-compose` is available. "
        "Use --no-db and seed the hardware session yourself."
    )


def psql(sql: str, *, quiet: bool = False) -> str:
    """Run one SQL string in the compose `postgres` service, return stdout."""
    cmd = [
        *_compose_cmd(),
        "--env-file",
        str(REPO_ROOT / ".env"),
        "-f",
        str(COMPOSE_FILE),
        "--project-directory",
        str(REPO_ROOT),
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        PG_USER,
        "-d",
        PG_DB,
        "-v",
        "ON_ERROR_STOP=1",
        "-t",
        "-A",
    ]
    result = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    if result.returncode != 0:
        if not quiet:
            sys.stderr.write(result.stderr)
        raise SystemExit(f"psql failed (exit {result.returncode})")
    return result.stdout.strip()


def seed_hardware_session(session_id: str, attempt_id: str) -> None:
    """Idempotently create a hardware rehab_session + open attempt + 3 devices."""
    devices = ",\n        ".join(
        f"('sensor-hw-{role}-{session_id}', '{ORG_ID}', 'hw-{role}', 'WT901BLE68')"
        for role in ROLES
    )
    sql = f"""
    INSERT INTO rehab_sessions (id, organization_id, episode_id, source_kind, started_at)
    VALUES ('{session_id}', '{ORG_ID}', '{EPISODE_ID}', 'hardware', CURRENT_TIMESTAMP)
    ON CONFLICT (id) DO NOTHING;

    INSERT INTO exercise_attempts
        (id, organization_id, rehab_session_id, exercise_prescription_id, started_at)
    VALUES ('{attempt_id}', '{ORG_ID}', '{session_id}', '{PRESCRIPTION_ID}', CURRENT_TIMESTAMP)
    ON CONFLICT (id) DO NOTHING;

    INSERT INTO sensor_devices (id, organization_id, device_identifier, model)
    VALUES
        {devices}
    ON CONFLICT (organization_id, device_identifier) DO NOTHING;
    """
    psql(sql)


def read_back(session_id: str, attempt_id: str) -> None:
    packets = psql(
        f"SELECT count(*) FROM gateway_packet_events WHERE rehab_session_id = '{session_id}';"
    )
    shadows = psql(
        f"SELECT count(*) FROM shadow_predictions WHERE exercise_attempt_id = '{attempt_id}';"
    )
    print(f"\n  DB gateway_packet_events for session : {packets}")
    print(f"  DB shadow_predictions for attempt   : {shadows}")
    latest = psql(
        "SELECT jsonb_pretty(prediction) FROM shadow_predictions "
        f"WHERE exercise_attempt_id = '{attempt_id}' ORDER BY created_at DESC LIMIT 1;"
    )
    if latest:
        print("\n  latest shadow_predictions.prediction row:")
        print("\n".join("    " + line for line in latest.splitlines()))


# --- capture -> packets ------------------------------------------------------


def resolve_capture(value: str) -> Path:
    path = Path(value)
    if path.is_file():
        return path
    candidate = DEFAULT_CAPTURE_DIR / value
    if candidate.is_file():
        return candidate
    raise SystemExit(f"Capture not found: {value} (looked in {DEFAULT_CAPTURE_DIR})")


def record_to_packet(record: dict[str, Any], session_id: str, sequence: int) -> dict[str, Any]:
    role = str(record["sensor"]["role"])
    if role not in ROLES:
        raise ValueError(f"unexpected sensor role {role!r}")
    accel = record["accelerometer_raw"]
    gyro = record["gyroscope_raw"]
    return {
        "session_id": session_id,
        "device_id": f"hw-{role}",
        "sensor_role": role,
        "timestamp_device": None,
        "timestamp_gateway": record["gateway_timestamp"],
        "sequence_number": sequence,
        "ax": int(accel[0]),
        "ay": int(accel[1]),
        "az": int(accel[2]),
        "gx": int(gyro[0]),
        "gy": int(gyro[1]),
        "gz": int(gyro[2]),
        "orientation_euler_degrees": [float(v) for v in record["euler_degrees"]],
        "battery": None,
        "origin": "hardware",
        "validation_status": str(record.get("validation_status") or "unverified_checksum"),
        "adapter_version": ADAPTER_VERSION,
    }


def post_packet(
    api_url: str, token: str, packet: dict[str, Any]
) -> tuple[int, dict[str, Any] | None]:
    body = json.dumps(packet).encode("utf-8")
    request = urllib.request.Request(
        f"{api_url}/api/v1/gateway/imu-packets",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        try:
            return error.code, json.loads(detail)
        except json.JSONDecodeError:
            return error.code, {"detail": detail}
    except urllib.error.URLError as error:
        raise SystemExit(f"Cannot reach API at {api_url}: {error.reason}")


def replay(args: argparse.Namespace) -> int:
    captures = (
        sorted(DEFAULT_CAPTURE_DIR.glob("*.jsonl"))
        if args.all
        else [resolve_capture(args.capture)]
    )
    captures = [path for path in captures if path.stat().st_size > 0]
    if not captures:
        raise SystemExit("No non-empty capture files to replay.")

    for capture in captures:
        stem = capture.stem
        session_id = args.session_id or f"hardware-replay-{stem}"
        attempt_id = f"{session_id}-attempt"
        print(f"\n=== {capture.name}  ->  session {session_id} ===")

        if not args.no_db:
            print("  seeding hardware session (idempotent) ...")
            seed_hardware_session(session_id, attempt_id)

        sequences = {role: 0 for role in ROLES}
        delivered = duplicates = errors = 0
        last_ok: dict[str, Any] | None = None
        first_error: dict[str, Any] | None = None

        lines = capture.read_text(encoding="utf-8").splitlines()
        if args.limit:
            lines = lines[: args.limit]
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            record = json.loads(raw)
            role = str(record["sensor"]["role"])
            packet = record_to_packet(record, session_id, sequences[role])
            sequences[role] += 1
            status, payload = post_packet(args.api_url, args.token, packet)
            if status in (200, 202):
                delivered += 1
                last_ok = payload
            elif status == 409:
                duplicates += 1
            else:
                errors += 1
                if first_error is None:
                    first_error = {"status": status, "payload": payload}
            if args.sleep:
                time.sleep(args.sleep)

        print(f"  delivered={delivered}  duplicates(409)={duplicates}  errors={errors}")
        if first_error is not None:
            print(f"  first error: {json.dumps(first_error, ensure_ascii=False)}")
        if duplicates and not delivered:
            print(
                "  every packet was a duplicate -- this session was already "
                "replayed. Pass a new --session-id to replay from scratch."
            )

        if last_ok is not None:
            sq = last_ok.get("signal_quality") or {}
            sp = last_ok.get("shadow_prediction")
            print("\n  last successful ingest response:")
            print(
                "    signal_quality: level={} scoring_permitted={} reasons={}".format(
                    sq.get("level"),
                    sq.get("scoring_permitted"),
                    sq.get("reasons"),
                )
            )
            _pp = json.dumps(last_ok.get("preprocessing"), ensure_ascii=False)
            print(f"    preprocessing : {_pp}")
            if sp is None:
                print("    shadow_prediction: null (ML branch did not run)")
            else:
                print("    shadow_prediction:")
                print(
                    "\n".join(
                        "      " + line
                        for line in json.dumps(sp, ensure_ascii=False, indent=2).splitlines()
                    )
                )

        if not args.no_db:
            read_back(session_id, attempt_id)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--capture",
        default="capture-01.jsonl",
        help="capture file name (under services/imu-gateway/captures/) or a path",
    )
    parser.add_argument("--all", action="store_true", help="replay every *.jsonl capture")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument(
        "--token",
        default=DOTENV.get("PHOENIX_GATEWAY_TOKEN", DEFAULT_TOKEN),
        help="gateway bearer token (default: from .env)",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="override the rehab_sessions id (use a fresh one to replay again)",
    )
    parser.add_argument("--limit", type=int, default=0, help="stop after N packets (0 = all)")
    parser.add_argument("--sleep", type=float, default=0.0, help="seconds to wait between packets")
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="skip DB seeding and read-back (HTTP only); seed the hardware session yourself",
    )
    args = parser.parse_args()
    return replay(args)


if __name__ == "__main__":
    raise SystemExit(main())
