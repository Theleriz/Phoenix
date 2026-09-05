import json
import sys
import threading
import unittest
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from server import build_server


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


class BiomechanicsHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = build_server("127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_healthcheck_declares_non_clinical_capabilities(self) -> None:
        connection = HTTPConnection("127.0.0.1", self.port)
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        payload = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertFalse(payload["clinical_scoring"])
        self.assertIn("resampling", payload["capabilities"])

    def test_preprocess_returns_filtered_frames_when_gate_is_open(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        request = {
            "signal_quality": {"scoring_permitted": True},
            "events": [
                event(role, started + timedelta(milliseconds=50 * index), index)
                for role in ("thigh", "shank", "foot")
                for index in range(3)
            ],
        }
        connection = HTTPConnection("127.0.0.1", self.port)
        connection.request(
            "POST",
            "/v1/preprocess",
            body=json.dumps(request),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertTrue(payload["allowed"])
        self.assertFalse(payload["clinical_scoring"])
        self.assertEqual(payload["frames"][1]["sensors"]["foot"]["gz"], 1.0)
