import unittest
from pathlib import Path


class IdentityInvitationTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).parents[1]
        self.api_source = (root / "app" / "main.py").read_text(encoding="utf-8")

    def _function(self, name: str) -> str:
        start = self.api_source.index(f"def {name}(")
        next_app = self.api_source.find("\n@app.", start)
        end = next_app if next_app != -1 else len(self.api_source)
        return self.api_source[start:end]

    def test_audit_is_always_written_on_the_request_transaction(self) -> None:
        # The only audit path is _insert_audit(cursor, ...); the old
        # write_audit() helper that opened its own connection is gone, so an
        # audit row can no longer be lost independently of its action.
        self.assertNotIn("def write_audit(", self.api_source)
        self.assertNotIn("write_audit(", self.api_source)
        self.assertIn("def _insert_audit(", self.api_source)

    def test_every_mutating_endpoint_audits_inside_its_own_cursor(self) -> None:
        for name in (
            "login",
            "create_invitation",
            "accept_invitation",
            "create_protocol_version",
            "submit_symptom_check",
            "create_alert_action",
            "start_exercise_attempt",
            "complete_exercise_attempt",
            "register_sensor_device",
        ):
            body = self._function(name)
            self.assertIn("_insert_audit(\n            cursor,", body, name)

    def test_patient_data_reads_are_audited(self) -> None:
        for name, event in (
            ("get_patient", "patient_view"),
            ("get_current_patient", "patient_self_view"),
            ("list_patients", "patients_list_view"),
            ("get_current_protocol", "protocol_view"),
            ("get_protocol_history", "protocol_history_view"),
            ("get_signal_quality", "signal_quality_view"),
            ("list_alerts", "alerts_view"),
        ):
            body = self._function(name)
            self.assertIn("_insert_audit(", body, name)
            self.assertIn(f'"{event}"', body, name)

    def test_invitation_cannot_reset_a_foreign_users_password(self) -> None:
        create = self._function("create_invitation")
        accept = self._function("accept_invitation")
        # Rejection at invite time and again at accept time.
        for body in (create, accept):
            self.assertIn("already exists outside this organization", body)
            self.assertIn("status_code=409", body)
        # The accept-time guard must run before the ON CONFLICT password write.
        self.assertLess(
            accept.index("already exists outside this organization"),
            accept.index("ON CONFLICT (email) DO UPDATE SET"),
        )
        # The recovery path is still allowed for an existing member of this org.
        self.assertIn("m.organization_id = %s", accept)


if __name__ == "__main__":
    unittest.main()
