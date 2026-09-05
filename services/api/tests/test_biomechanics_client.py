import asyncio
import sys
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

root = Path(__file__).parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root.parent / "biomechanics"))

from app.biomechanics import BiomechanicsClient, PreprocessingUnavailable  # noqa: E402
from server import build_server  # noqa: E402


def event(role: str, timestamp: datetime, value: int) -> dict[str, object]:
    return {
        "sensor_role": role,
        "timestamp_gateway": timestamp.isoformat(),
        "ax": value,
        "ay": value,
        "az": value,
        "gx": value,
        "gy": value,
        "gz": value,
    }


class BiomechanicsClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = build_server("127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1/preprocess"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_sends_technically_permitted_events_to_preprocessor(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=50 * index), index)
            for role in ("thigh", "shank", "foot")
            for index in range(3)
        ]
        result = asyncio.run(
            BiomechanicsClient(self.url).preprocess(
                events=events, signal_quality={"scoring_permitted": True}
            )
        )
        self.assertTrue(result["allowed"])
        self.assertFalse(result["clinical_scoring"])

    def test_unavailable_service_raises_domain_error(self) -> None:
        with self.assertRaises(PreprocessingUnavailable):
            client = BiomechanicsClient("http://127.0.0.1:1/v1/preprocess", timeout_seconds=0.1)
            asyncio.run(
                client.preprocess(events=[], signal_quality={"scoring_permitted": True})
            )
