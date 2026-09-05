"""Capture non-clinical WT901BLE68 BLE angles packets into an anonymised JSONL file.

Example:
  python capture_wt901ble68.py --seconds 60 --output captures/baseline.jsonl \
    --sensor thigh=AA:BB:CC:DD:EE:01 --sensor shank=AA:BB:CC:DD:EE:02 \
    --sensor foot=AA:BB:CC:DD:EE:03
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from time import monotonic_ns

sys.path.insert(0, str(Path(__file__).parent / "src"))

from phoenix_imu_gateway.wt901ble68 import AnglesFramer, parse_angles_frame

SERVICE_UUID = "0000ffe5-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffe4-0000-1000-8000-00805f9b34fb"
ROLES = {"thigh", "shank", "foot"}


def parse_sensor(value: str) -> tuple[str, str]:
    role, separator, address = value.partition("=")
    if separator != "=" or role.lower() not in ROLES or not address:
        raise argparse.ArgumentTypeError("Use --sensor thigh=ADDRESS, shank=ADDRESS or foot=ADDRESS")
    return role.lower(), address


async def capture(sensors: dict[str, str], output: Path, seconds: float) -> Counter[str]:
    try:
        from bleak import BleakClient
    except ImportError as error:
        raise RuntimeError("Install BLE support: pip install -e .[ble]") from error

    output.parent.mkdir(parents=True, exist_ok=True)
    counters: Counter[str] = Counter()
    framers = {role: AnglesFramer() for role in sensors}
    sequence = Counter()
    clients = []
    with output.open("x", encoding="utf-8") as stream:
        def notification(role: str):
            def handle(_: int, payload: bytearray) -> None:
                for raw in framers[role].feed(bytes(payload)):
                    try:
                        frame = parse_angles_frame(raw)
                    except ValueError:
                        counters[f"{role}_invalid"] += 1
                        continue
                    sequence[role] += 1
                    record = {
                        "record_type": "wt901ble68_angles_capture",
                        "origin": "hardware_diagnostic",
                        "clinical_use": False,
                        "sensor_role": role,
                        "sequence_number": sequence[role],
                        "host_timestamp_utc": datetime.now(UTC).isoformat(),
                        "host_monotonic_ns": monotonic_ns(),
                        "raw_hex": raw.hex(),
                        "checksum_valid": True,
                        "angles_degrees": {"roll": frame.roll_degrees, "pitch": frame.pitch_degrees, "yaw": frame.yaw_degrees},
                        "packet_version": frame.version,
                    }
                    stream.write(json.dumps(record, separators=(",", ":")) + "\n")
                    stream.flush()
                    counters[role] += 1
            return handle

        try:
            for role, address in sensors.items():
                client = BleakClient(address)
                await client.connect()
                if not client.is_connected:
                    raise RuntimeError(f"Could not connect {role} ({address})")
                await client.start_notify(CHARACTERISTIC_UUID, notification(role))
                clients.append(client)
            await asyncio.sleep(seconds)
        finally:
            for client in reversed(clients):
                try:
                    await client.stop_notify(CHARACTERISTIC_UUID)
                    await client.disconnect()
                except Exception as error:  # cleanup must not discard an existing capture
                    print(f"Cleanup warning: {error}", file=sys.stderr)
    return counters


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostic WT901BLE68 angles capture; not clinical use.")
    parser.add_argument("--sensor", action="append", type=parse_sensor, required=True)
    parser.add_argument("--seconds", type=float, default=60, help="Capture duration; default: 60")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sensors = dict(args.sensor)
    if set(sensors) != ROLES:
        parser.error("Provide exactly one --sensor for each role: thigh, shank, foot")
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    if args.output.exists():
        parser.error(f"Refusing to overwrite existing capture: {args.output}")
    print(f"Connecting three sensors through {SERVICE_UUID}; capture is non-clinical.")
    counters = asyncio.run(capture(sensors, args.output, args.seconds))
    print(f"Saved {sum(counters[role] for role in ROLES)} valid frames to {args.output}")
    print(dict(counters))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
