"""Structural checks for the React clinician cabinet interface."""
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "src" / "main.tsx"


class ClinicianWebTests(unittest.TestCase):
    def test_clinician_views_and_locales_are_present(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        required_markers = (
            "dashboard", "patient", "prescription", "alerts", "messages", "kz:", "en:",
        )
        for required in required_markers:
            self.assertIn(required, page)

    def test_prescription_editor_is_interactive(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("saveVersion", page)
        self.assertIn("setHistory", page)

    def test_review_queue_supports_acknowledge_and_dismiss(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("acknowledge", page.lower())
        self.assertIn("dismiss", page.lower())

    def test_demo_data_is_explicitly_non_clinical(self) -> None:
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("not used for clinical decisions", page)


if __name__ == "__main__":
    unittest.main()
