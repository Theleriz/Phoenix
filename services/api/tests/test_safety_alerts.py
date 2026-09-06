import unittest
from pathlib import Path


class SafetyAlertsTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).parents[1]
        self.api_source = (root / "app" / "main.py").read_text(encoding="utf-8")
        migration_path = root / "migrations" / "versions" / "0013_safety_rule_policies.sql"
        self.policy_migration = migration_path.read_text(encoding="utf-8")
        lineage_path = root / "migrations" / "versions" / "0002_data_lineage.sql"
        self.lineage_migration = lineage_path.read_text(encoding="utf-8")
        assessments_path = root / "migrations" / "versions" / "0014_safety_assessments.sql"
        self.assessments_migration = assessments_path.read_text(encoding="utf-8")
        start = self.api_source.index("def submit_symptom_check(")
        end = self.api_source.index("\n@app.", start)
        self.symptom_check_fn = self.api_source[start:end]

    def test_symptom_check_endpoint_evaluates_the_deterministic_engine(self) -> None:
        self.assertIn('"/api/v1/rehab-sessions/{session_id}/symptom-check"', self.api_source)
        self.assertIn("INSERT INTO symptom_checks", self.api_source)
        self.assertIn("evaluate_safety_rules", self.api_source)
        self.assertIn("SafetyRulePolicy.from_configuration", self.api_source)
        self.assertLess(
            self.api_source.index("INSERT INTO symptom_checks"),
            self.api_source.index("result = evaluate_safety_rules("),
        )

    def test_alert_is_only_created_for_yellow_or_red(self) -> None:
        self.assertIn('if assessment["level"] in ("YELLOW", "RED"):', self.api_source)
        self.assertIn("INSERT INTO alerts", self.api_source)

    def test_symptom_check_workflow_runs_in_a_single_transaction(self) -> None:
        # The check, the assessment, the alert and both audit rows must share
        # one connection so a downstream failure cannot leave a RED check with
        # no alert or no audit trail.
        self.assertEqual(self.symptom_check_fn.count("psycopg.connect("), 1)
        self.assertNotIn("write_audit(", self.symptom_check_fn)
        self.assertEqual(self.symptom_check_fn.count("_insert_audit("), 2)
        self.assertIn("INSERT INTO safety_assessments", self.symptom_check_fn)
        self.assertLess(
            self.symptom_check_fn.index("INSERT INTO alerts"),
            self.symptom_check_fn.index("INSERT INTO safety_assessments"),
        )

    def test_every_outcome_is_persisted_as_a_safety_assessment(self) -> None:
        # safety_assessments is written unconditionally, outside the YELLOW/RED
        # branch, so GREEN and withheld results also get a lineage row.
        branch = self.symptom_check_fn.index('if assessment["level"] in ("YELLOW", "RED"):')
        insert = self.symptom_check_fn.index("INSERT INTO safety_assessments")
        self.assertGreater(insert, branch)
        assessment_line = next(
            line
            for line in self.symptom_check_fn.splitlines()
            if "INSERT INTO safety_assessments" in line
        )
        self.assertEqual(len(assessment_line) - len(assessment_line.lstrip()), 12)

    def test_malformed_policy_is_withheld_not_a_server_error(self) -> None:
        self.assertIn("except ValueError as error:", self.symptom_check_fn)
        self.assertIn('"status": "withheld"', self.symptom_check_fn)
        self.assertIn("policy_invalid:", self.symptom_check_fn)

    def test_safety_assessments_table_is_append_only_and_lineage_linked(self) -> None:
        migration = self.assessments_migration
        self.assertIn("CREATE TABLE safety_assessments", migration)
        self.assertIn("safety_assessments_immutable", migration)
        self.assertIn("symptom_check_id TEXT NOT NULL REFERENCES symptom_checks(id)", migration)
        self.assertIn("policy_version TEXT", migration)
        self.assertIn("alert_id TEXT REFERENCES alerts(id)", migration)

    def test_alert_actions_are_append_only_and_role_gated(self) -> None:
        self.assertIn('"/api/v1/alerts/{alert_id}/actions"', self.api_source)
        self.assertIn("require_roles(identity, ALERT_ACTION_ROLES)", self.api_source)
        self.assertIn("INSERT INTO clinician_actions", self.api_source)
        self.assertNotIn("UPDATE alerts", self.api_source)
        self.assertNotIn("DELETE FROM alerts", self.api_source)

    def test_alerts_list_status_derives_from_latest_clinician_action(self) -> None:
        self.assertIn('"/api/v1/episodes/{episode_id}/alerts"', self.api_source)
        self.assertIn("ORDER BY ca.created_at DESC LIMIT 1", self.api_source)
        self.assertIn('"status": row[5] or "open"', self.api_source)

    def test_safety_rule_policy_is_versioned_and_starts_unapproved(self) -> None:
        self.assertIn("CREATE TABLE safety_rule_policies", self.policy_migration)
        self.assertIn("safety_rule_policies_immutable", self.policy_migration)
        self.assertIn('"approval_state": "draft"', self.policy_migration)

    def test_symptom_checks_and_alerts_tables_already_declared_in_lineage(self) -> None:
        self.assertIn("CREATE TABLE symptom_checks", self.lineage_migration)
        self.assertIn("CREATE TABLE alerts", self.lineage_migration)
        self.assertIn("CREATE TABLE clinician_actions", self.lineage_migration)
        self.assertIn("clinician_actions_immutable", self.lineage_migration)


if __name__ == "__main__":
    unittest.main()
