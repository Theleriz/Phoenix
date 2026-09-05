"""Development-only synthetic replay delivered to the local API when configured."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from phoenix_imu_gateway.delivery import HttpJsonSender, deliver_packets, flush_buffer
from phoenix_imu_gateway.synthetic import build_synthetic_replay, packet_as_json
from phoenix_imu_gateway.transport import DurableBuffer


async def main() -> None:
    url = os.environ.get("PHOENIX_IMU_INGEST_URL")
    token = os.environ.get("PHOENIX_GATEWAY_TOKEN")
    buffer_path = os.environ.get("PHOENIX_IMU_BUFFER_PATH", "/tmp/phoenix-imu.jsonl")
    buffer = DurableBuffer(Path(buffer_path))
    sender = HttpJsonSender(url, bearer_token=token) if url and token else None
    while True:
        replay = build_synthetic_replay()
        for sensor in await replay.discover():
            await replay.connect(sensor.sensor_id)
        packets = [packet async for packet in replay.stream()]
        if sender is None:
            for packet in packets:
                print(packet_as_json(packet), flush=True)
        else:
            await flush_buffer(send=sender, buffer=buffer)
            result = await deliver_packets(packets, send=sender, buffer=buffer)
            print(
                f"synthetic replay delivered={result.delivered} buffered={result.buffered}",
                flush=True,
            )
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
