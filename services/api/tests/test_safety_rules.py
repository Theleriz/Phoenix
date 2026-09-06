import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.safety_rules import (
    SafetyAssessmentStatus,
    SafetyLevel,
    SafetyRulePolicy,
    evaluate_safety_rules,
)


def approved_policy(**overrides: object) -> SafetyRulePolicy:
    configuration: dict[str, object] = {
        "version": "org-demo-safety-v1",
        "approval_state": "clinically_approved",
        "red_symptom_keys": ["chest_pain", "shortness_of_breath", "calf_pain"],
        "yellow_symptom_keys": ["swelling", "redness", "drainage"],
        "pain_increase_yellow_threshold": 3,
        **overrides,
    }
    return SafetyRulePolicy.from_configuration(configuration)


class SafetyRulesTests(unittest.TestCase):
    def test_draft_policy_withholds_any_result(self) -> None:
        policy = SafetyRulePolicy.from_configuration({"version": "draft-v1"})
        result = evaluate_safety_rules(
            policy=policy, reported_symptoms=frozenset({"chest_pain"})
        )
        self.assertEqual(result.status, SafetyAssessmentStatus.WITHHELD)
        self.assertIsNone(result.level)

    def test_no_reported_symptoms_and_stable_pain_is_green(self) -> None:
        result = evaluate_safety_rules(
            policy=approved_policy(),
            reported_symptoms=frozenset(),
            pain_before=3,
            pain_after=3,
        )
        self.assertEqual(result.status, SafetyAssessmentStatus.EVALUATED)
        self.assertEqual(result.level, SafetyLevel.GREEN)
        self.assertEqual(result.reasons, ())

    def test_red_symptom_wins_over_yellow_symptom(self) -> None:
        result = evaluate_safety_rules(
            policy=approved_policy(),
            reported_symptoms=frozenset({"swelling", "chest_pain"}),
        )
        self.assertEqual(result.level, SafetyLevel.RED)
        self.assertIn("red_symptom:chest_pain", result.reasons)
        self.assertIn("yellow_symptom:swelling", result.reasons)

    def test_yellow_symptom_without_red_is_yellow(self) -> None:
        result = evaluate_safety_rules(
            policy=approved_policy(), reported_symptoms=frozenset({"redness"})
        )
        self.assertEqual(result.level, SafetyLevel.YELLOW)
        self.assertEqual(result.reasons, ("yellow_symptom:redness",))

    def test_pain_increase_at_or_above_threshold_is_yellow(self) -> None:
        result = evaluate_safety_rules(
            policy=approved_policy(),
            reported_symptoms=frozenset(),
            pain_before=3,
            pain_after=6,
        )
        self.assertEqual(result.level, SafetyLevel.YELLOW)
        self.assertIn("pain_increase_at_or_above_threshold", result.reasons)

    def test_pain_increase_below_threshold_stays_green(self) -> None:
        result = evaluate_safety_rules(
            policy=approved_policy(),
            reported_symptoms=frozenset(),
            pain_before=3,
            pain_after=5,
        )
        self.assertEqual(result.level, SafetyLevel.GREEN)

    def test_unconfigured_symptom_defaults_to_yellow_review_not_green(self) -> None:
        result = evaluate_safety_rules(
            policy=approved_policy(), reported_symptoms=frozenset({"dizziness"})
        )
        self.assertEqual(result.level, SafetyLevel.YELLOW)
        self.assertEqual(result.reasons, ("unconfigured_symptom:dizziness",))

    def test_policy_rejects_a_key_configured_as_both_red_and_yellow(self) -> None:
        with self.assertRaises(ValueError):
            approved_policy(red_symptom_keys=["swelling"], yellow_symptom_keys=["swelling"])

    def test_policy_requires_a_version(self) -> None:
        with self.assertRaises(ValueError):
            SafetyRulePolicy.from_configuration({})


if __name__ == "__main__":
    unittest.main()
