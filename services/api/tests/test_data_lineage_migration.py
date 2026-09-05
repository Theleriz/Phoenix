import unittest
from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0002_data_lineage.sql"
).read_text(encoding="utf-8")


class DataLineageMigrationTests(unittest.TestCase):
    def test_declares_required_lineage_entities(self) -> None:
        for table in (
            "episodes_of_care",
            "rehab_sessions",
            "exercise_attempts",
            "raw_imu_chunks",
            "derived_metrics",
            "exercise_scores",
            "audit_events",
        ):
            self.assertIn(f"CREATE TABLE {table}", MIGRATION)

    def test_protects_append_only_entities(self) -> None:
        self.assertIn("raw_imu_chunks_immutable", MIGRATION)
        self.assertIn("exercise_scores_immutable", MIGRATION)
        self.assertIn("clinician_actions_immutable", MIGRATION)


if __name__ == "__main__":
    unittest.main()
