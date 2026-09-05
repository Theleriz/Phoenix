import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.deterministic_scoring import (
    ScorePolicy,
    ScoreStatus,
    calculate_deterministic_score,
)


class DeterministicScoringTests(unittest.TestCase):
    def test_draft_formula_cannot_calculate_a_score(self) -> None:
        policy = ScorePolicy.from_configuration({"version": "draft-v1"})
        result = calculate_deterministic_score(
            policy=policy,
            components={},
            signal_quality={"scoring_permitted": True},
        )
        self.assertEqual(result.status, ScoreStatus.WITHHELD)
        self.assertEqual(result.reason, "formula_not_clinically_approved")

    def test_quality_gate_withholds_even_an_approved_formula(self) -> None:
        policy = ScorePolicy.from_configuration(
            {
                "version": "approved-v1",
                "approval_state": "clinically_approved",
                "weights": {"rom": 1},
            }
        )
        result = calculate_deterministic_score(
            policy=policy,
            components={"rom": 1.0},
            signal_quality={"scoring_permitted": False},
        )
        self.assertEqual(result.reason, "signal_quality_gate_closed")

    def test_approved_complete_formula_is_reproducible(self) -> None:
        policy = ScorePolicy.from_configuration(
            {
                "version": "approved-v1",
                "approval_state": "clinically_approved",
                "weights": {"component_a": 0.25, "component_b": 0.75},
            }
        )
        result = calculate_deterministic_score(
            policy=policy,
            components={"component_a": 0.4, "component_b": 0.8},
            signal_quality={"scoring_permitted": True},
        )
        self.assertEqual(result.status, ScoreStatus.CALCULATED)
        self.assertEqual(result.value, 0.7)
        self.assertFalse(result.ml_component_included)
