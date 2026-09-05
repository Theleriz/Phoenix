import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.security import can_view_patient, issue_token, verify_token


class SecurityTests(unittest.TestCase):
    def test_token_is_tenant_scoped_and_rejects_wrong_secret(self) -> None:
        token = issue_token(user_id="user-a", organization_id="org-a", secret="secret-a")

        self.assertEqual(verify_token(token, secret="secret-a")["organization_id"], "org-a")
        self.assertIsNone(verify_token(token, secret="other-secret"))

    def test_patient_can_only_view_own_record_without_privileged_role(self) -> None:
        self.assertTrue(
            can_view_patient(
                roles=frozenset({"patient"}), patient_user_id="user-a", user_id="user-a"
            )
        )
        self.assertFalse(
            can_view_patient(
                roles=frozenset({"patient"}), patient_user_id="user-b", user_id="user-a"
            )
        )
        self.assertTrue(
            can_view_patient(
                roles=frozenset({"clinician"}), patient_user_id="user-b", user_id="user-a"
            )
        )


if __name__ == "__main__":
    unittest.main()
