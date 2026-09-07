import unittest
from pathlib import Path


class PatientSelfServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).parents[1]
        self.api_source = (root / "app" / "main.py").read_text(encoding="utf-8")
        self.protocol_seed = (
            root / "migrations" / "versions" / "0004_protocol_engine.sql"
        ).read_text(encoding="utf-8")
        self.gateway_seed = (
            root / "migrations" / "versions" / "0006_gateway_ingestion.sql"
        ).read_text(encoding="utf-8")

    def test_patients_me_is_registered_before_the_parameterised_route(self) -> None:
        # FastAPI/Starlette matches routes in registration order: "/me" would
        # be swallowed as a {patient_id} value if the dynamic route came first.
        self.assertLess(
            self.api_source.index('"/api/v1/patients/me"'),
            self.api_source.index('"/api/v1/patients/{patient_id}"'),
        )

    def test_patient_list_is_role_gated_to_clinical_staff(self) -> None:
        self.assertIn(
            'PATIENT_LIST_ROLES = frozenset({"clinician", "rehabilitologist", '
            '"organization_admin"})',
            self.api_source,
        )
        self.assertIn("require_roles(identity, PATIENT_LIST_ROLES)", self.api_source)

    def test_exercise_attempt_requires_a_prescription_scoped_to_the_episode(self) -> None:
        self.assertIn('"/api/v1/episodes/{episode_id}/exercise-attempts"', self.api_source)
        self.assertIn(
            "JOIN protocol_assignments pa ON pa.id = ep.protocol_assignment_id", self.api_source
        )
        self.assertIn("Unknown exercise prescription for this episode", self.api_source)

    def test_exercise_attempt_completion_only_closes_an_open_attempt(self) -> None:
        self.assertIn(
            "UPDATE exercise_attempts SET ended_at = CURRENT_TIMESTAMP\n"
            "               WHERE id = %s AND ended_at IS NULL",
            self.api_source,
        )

    def test_sensor_device_registration_is_an_idempotent_upsert(self) -> None:
        self.assertIn('"/api/v1/sensor-devices"', self.api_source)
        self.assertIn("ON CONFLICT (organization_id, device_identifier)", self.api_source)
        self.assertIn("DO UPDATE SET model = EXCLUDED.model", self.api_source)

    def test_active_episode_lookup_does_not_assume_a_specific_status_value(self) -> None:
        # episodes_of_care.status is free text (migration 0002), and the
        # seeded demo episode (0004) uses "development_fixture", not
        # "active" -- filtering on a literal status string here would make
        # /patients/me unable to find that episode at all.
        self.assertIn("def _active_episode_id(", self.api_source)
        body = self.api_source[self.api_source.index("def _active_episode_id(") :]
        body = body[: body.index("\n\n\n")]
        self.assertNotIn("status = 'active'", body)
        self.assertNotIn("status =", body)

    def test_existing_demo_seed_already_gives_the_demo_patient_an_episode_and_devices(self) -> None:
        # These rows predate this feature (0004/0006) -- self-lookup and
        # exercise-attempt creation must work against them without a new,
        # redundant seed migration.
        self.assertIn("episode-demo", self.protocol_seed)
        self.assertIn("protocol-assignment-demo-v1", self.protocol_seed)
        self.assertIn("prescription-heel-slide-demo-v1", self.protocol_seed)
        for role in ("thigh", "shank", "foot"):
            self.assertIn(f"synthetic-{role}", self.gateway_seed)


if __name__ == "__main__":
    unittest.main()
