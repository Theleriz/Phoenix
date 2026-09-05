"""Structural checks for the React patient replay interface."""
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "src" / "main.tsx"

class PatientWebTests(unittest.TestCase):
    def test_patient_flow_and_locales_are_present(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        required_markers = (
            "today", "setup", "calibration", "exercise", "result",
            "check", "progress", "messages", "kz:", "en:",
        )
        for required in required_markers:
            self.assertIn(required, page)

    def test_synthetic_replay_is_not_a_clinical_score(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("not used for scoring, alerts, or clinical decisions", page)
        self.assertIn("notCalculated", page)

if __name__ == "__main__":
    unittest.main()
