import unittest
from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0004_protocol_engine.sql"
).read_text(encoding="utf-8")
CATALOG = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0005_exercise_catalog.sql"
).read_text(encoding="utf-8")


class ProtocolMigrationTests(unittest.TestCase):
    def test_protocol_configuration_has_required_stage_five_fields(self) -> None:
        for field in (
            "required_sensors",
            "reference_video",
            "primary_metrics",
            "secondary_metrics",
            "prescription_schema",
            "valid_repetition_definition",
            "stop_conditions",
            "live_feedback_whitelist",
            "scoring_formula",
            "limitations",
        ):
            self.assertIn(field, MIGRATION)

    def test_catalog_contains_first_five_exercises_as_drafts(self) -> None:
        for exercise in (
            "Short Arc Quad",
            "Ankle Pumps",
            "Straight Leg Raise",
            "Prone Knee Bend",
        ):
            self.assertIn(exercise, CATALOG)
        self.assertEqual(CATALOG.count('"approval_state":"draft"'), 4)

    def test_assignment_versions_are_append_only_in_api(self) -> None:
        api = (Path(__file__).parents[1] / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("protocol-history", api)
        self.assertIn("superseded_at IS NULL", api)
        self.assertIn("clinician[0]", api)


if __name__ == "__main__":
    unittest.main()
