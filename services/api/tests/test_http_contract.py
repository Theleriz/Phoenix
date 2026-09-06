"""End-to-end HTTP contract checks that actually execute the FastAPI app.

Unlike the source-string assertions in the other suites, these instantiate the
real application and drive it through ``TestClient`` / the Pydantic models, so
routing, request validation and auth rejection are exercised for real.

The module is skipped where ``fastapi`` / ``psycopg`` are not installed (the
lightweight lint+unit environment). Install ``requirements.txt`` plus
``requirements-dev.txt`` to run it. Paths that need a live database are further
guarded by ``PHOENIX_TEST_DATABASE_URL`` and are additive scaffolding for CI.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

_DEPS = all(importlib.util.find_spec(name) for name in ("fastapi", "psycopg", "httpx"))

if _DEPS:
    from app.main import MAX_REPORTED_SYMPTOMS, SymptomCheckRequest
    from pydantic import ValidationError


@unittest.skipUnless(_DEPS, "fastapi/psycopg/httpx not installed")
class HttpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("DATABASE_URL", "postgresql://unused/unused")
        os.environ.setdefault("API_AUTH_SECRET", "test-secret")
        os.environ.setdefault("PHOENIX_GATEWAY_TOKEN", "test-gateway-token")
        from app.main import app
        from fastapi.testclient import TestClient

        cls.client = TestClient(app)

    def _valid_packet(self, **overrides: object) -> dict[str, object]:
        packet: dict[str, object] = {
            "session_id": "s-1",
            "device_id": "d-1",
            "sensor_role": "thigh",
            "timestamp_gateway": "2026-01-01T00:00:00+00:00",
            "sequence_number": 0,
            "ax": 0, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0,
            "origin": "synthetic",
            "validation_status": "synthetic",
            "adapter_version": "v1",
        }
        packet.update(overrides)
        return packet

    def test_healthz_is_open(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_demo_snapshot_is_served(self) -> None:
        response = self.client.get("/api/v1/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn("safety_notice", response.json())

    def test_protected_route_without_bearer_is_rejected(self) -> None:
        response = self.client.get("/api/v1/auth/me")
        self.assertIn(response.status_code, (401, 403))

    def test_gateway_ingestion_requires_the_gateway_token(self) -> None:
        response = self.client.post("/api/v1/gateway/imu-packets", json=self._valid_packet())
        self.assertEqual(response.status_code, 401)

    def test_gateway_packet_schema_is_enforced(self) -> None:
        response = self.client.post(
            "/api/v1/gateway/imu-packets",
            json=self._valid_packet(sensor_role="elbow"),
            headers={"Authorization": "Bearer test-gateway-token"},
        )
        self.assertEqual(response.status_code, 422)

    def test_symptom_model_normalises_and_dedupes_symptoms(self) -> None:
        model = SymptomCheckRequest(
            reported_symptoms=[" Calf_Pain ", "calf_pain", "swelling"]
        )
        self.assertEqual(model.reported_symptoms, ["calf_pain", "swelling"])

    def test_symptom_model_rejects_free_text_symptoms(self) -> None:
        with self.assertRaises(ValidationError):
            SymptomCheckRequest(reported_symptoms=["chest pain!!!"])

    def test_symptom_model_caps_the_symptom_count(self) -> None:
        too_many = [f"sym_{i}" for i in range(MAX_REPORTED_SYMPTOMS + 1)]
        with self.assertRaises(ValidationError):
            SymptomCheckRequest(reported_symptoms=too_many)

    def test_symptom_model_enforces_pain_score_range(self) -> None:
        with self.assertRaises(ValidationError):
            SymptomCheckRequest(pain_before=99)


if __name__ == "__main__":
    unittest.main()
