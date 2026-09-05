"""Structural checks for the React patient replay interface."""
from pathlib import Path
import unittest

PAGE = Path(__file__).resolve().parents[1] / "src" / "main.tsx"

class PatientWebTests(unittest.TestCase):
    def test_patient_flow_and_locales_are_present(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        for required in ("today", "setup", "calibration", "exercise", "result", "check", "progress", "messages", "kz:", "en:"):
            self.assertIn(required, page)

    def test_synthetic_replay_is_not_a_clinical_score(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("not used for scoring, alerts, or clinical decisions", page)
        self.assertIn("notCalculated", page)

if __name__ == "__main__":
    unittest.main()
