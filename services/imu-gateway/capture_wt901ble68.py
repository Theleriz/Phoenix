"""Capture non-clinical WT901BLE68 BLE notifications into an anonymised JSONL file.

Parses the currently observed 20-byte `0x55 0x61` frame shape (no checksum
field), confirmed on real hardware on 2026-09-05 across all three sensor
roles. Every record is tagged `origin: "hardware"` and
`validation_status: "unverified_checksum"` by the shared
`phoenix_imu_gateway` parser. It does not calculate ROM, repetitions, score or
clinical feedback. Do not record patient identifiers in the output filename
or file contents.

Example:
  python capture_wt901ble68.py --seconds 60 --output captures/baseline.jsonl \
    --sensor thigh=AA:BB:CC:DD:EE:FF --sensor shank=AA:BB:CC:DD:EE:FE \
    --sensor foot=AA:BB:CC:DD:EE:FD
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from phoenix_imu_gateway.framing import WitMotion61FrameBuffer
from phoenix_imu_gateway.models import PacketOrigin, SensorInfo, SensorRole
from phoenix_imu_gateway.parser import FrameParseError, WitMotion61Parser
from phoenix_imu_gateway.synthetic import packet_as_json

SERVICE_UUID = "0000ffe5-0000-1000-8000-00805f9a34fb"
CHARACTERISTIC_UUID = "0000ffe4-0000-1000-8000-00805f9a34fb"
ROLES = {"thigh": SensorRole.THIGH, "shank": SensorRole.SHANK, "foot": SensorRole.FOOT}


def parse_sensor(value: str) -> tuple[str, str]:
    role, separator, address = value.partition("=")
    if separator != "=" or role.lower() not in ROLES or not address:
        raise argparse.ArgumentTypeError(
            "Use --sensor thigh=ADDRESS, shank=ADDRESS or foot=ADDRESS"
        )
    return role.lower(), address


async def capture(
    sensors: dict[str, str], output: Path, seconds: float, session_id: str
) -> Counter[str]:
    try:
        from bleak import BleakClient
    except ImportError as error:
        raise RuntimeError("Install BLE support: pip install -e .[ble]") from error

    output.parent.mkdir(parents=True, exist_ok=True)
    counters: Counter[str] = Counter()
    packet_parser = WitMotion61Parser()
    buffers = {role: WitMotion61FrameBuffer() for role in sensors}
    sequence: Counter[str] = Counter()
    clients = []
    with output.open("x", encoding="utf-8") as stream:
        def notification(role: str, sensor: SensorInfo):
            def handle(_: int, payload: bytearray) -> None:
                for raw in buffers[role].feed(bytes(payload)):
                    sequence[role] += 1
                    try:
                        packet = packet_parser.parse(
                            raw,
                            session_id=session_id,
                            sensor=sensor,
                            sequence_number=sequence[role],
                            origin=PacketOrigin.HARDWARE,
                        )
                    except FrameParseError:
                        counters[f"{role}_invalid"] += 1
                        continue
                    stream.write(packet_as_json(packet) + "\n")
                    stream.flush()
                    counters[role] += 1
            return handle

        try:
            for role, address in sensors.items():
                sensor = SensorInfo(
                    sensor_id=f"{role}-{address}",
                    role=ROLES[role],
                    address=address,
                    model="WT901BLE68",
                    service_uuid=SERVICE_UUID,
                    characteristic_uuid=CHARACTERISTIC_UUID,
                )
                client = BleakClient(address)
                await client.connect()
                if not client.is_connected:
                    raise RuntimeError(f"Could not connect {role} ({address})")
                await client.start_notify(CHARACTERISTIC_UUID, notification(role, sensor))
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
    parser = argparse.ArgumentParser(
        description="Diagnostic WT901BLE68 angles capture; not clinical use."
    )
    parser.add_argument("--sensor", action="append", type=parse_sensor, required=True)
    parser.add_argument("--seconds", type=float, default=60, help="Capture duration; default: 60")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--session-id",
        default="hardware-diagnostic-session",
        help=(
            "Non-clinical session label stored in each record; "
            "default: hardware-diagnostic-session"
        ),
    )
    args = parser.parse_args()
    sensors = dict(args.sensor)
    if set(sensors) != set(ROLES):
        parser.error("Provide exactly one --sensor for each role: thigh, shank, foot")
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    if args.output.exists():
        parser.error(f"Refusing to overwrite existing capture: {args.output}")
    print(f"Connecting three sensors through {SERVICE_UUID}; capture is non-clinical.")
    counters = asyncio.run(capture(sensors, args.output, args.seconds, args.session_id))
    print(f"Saved {sum(counters[role] for role in ROLES)} valid frames to {args.output}")
    print(dict(counters))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
