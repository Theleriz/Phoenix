import unittest
from pathlib import Path


class TkaScopeMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        path = Path(__file__).parents[1] / "migrations" / "versions" / "0012_tka_mvp_scope.sql"
        self.migration = path.read_text(encoding="utf-8")

    def test_limits_standard_mvp_data_to_primary_tka(self) -> None:
        self.assertIn("procedure_kind = 'primary_tka'", self.migration)
        self.assertIn("pathway_mode IN ('standard', 'clinician_managed')", self.migration)

    def test_records_clinician_context_without_auto_recommendations(self) -> None:
        self.assertIn("weight_bearing_status", self.migration)
        self.assertIn("precautions JSONB", self.migration)
        self.assertIn("next_visit_at", self.migration)
