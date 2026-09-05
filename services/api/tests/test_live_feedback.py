import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.live_feedback import CuePolicy, CueState, decide_cue


class LiveFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.at = datetime(2026, 1, 1, tzinfo=UTC)
        self.state = CueState()
        self.policy = CuePolicy.from_configuration(
            {
                "rule_version": "cue-rules-v1",
                "approval_state": "clinically_approved",
                "live_feedback_whitelist": ["check_sensors"],
                "debounce_observations": 2,
                "cooldown_seconds": 5,
            }
        )

    def test_draft_rule_never_emits_a_cue(self) -> None:
        draft = CuePolicy.from_configuration({"rule_version": "draft-v1"})
        result = decide_cue(
            candidate_cue="check_sensors",
            signal_quality={"scoring_permitted": True},
            policy=draft,
            state=self.state,
            observed_at=self.at,
        )
        self.assertIsNone(result.cue)
        self.assertEqual(result.reason, "rule_not_clinically_approved")

    def test_debounce_and_cooldown_limit_one_stable_cue(self) -> None:
        first = decide_cue(
            candidate_cue="check_sensors",
            signal_quality={"scoring_permitted": True},
            policy=self.policy,
            state=self.state,
            observed_at=self.at,
        )
        second = decide_cue(
            candidate_cue="check_sensors",
            signal_quality={"scoring_permitted": True},
            policy=self.policy,
            state=self.state,
            observed_at=self.at + timedelta(seconds=1),
        )
        third = decide_cue(
            candidate_cue="check_sensors",
            signal_quality={"scoring_permitted": True},
            policy=self.policy,
            state=self.state,
            observed_at=self.at + timedelta(seconds=2),
        )
        self.assertEqual(first.reason, "debounce_pending")
        self.assertEqual(second.cue, "check_sensors")
        self.assertEqual(third.reason, "cooldown_active")

    def test_quality_gate_clears_pending_cue(self) -> None:
        result = decide_cue(
            candidate_cue="check_sensors",
            signal_quality={"scoring_permitted": False},
            policy=self.policy,
            state=self.state,
            observed_at=self.at,
        )
        self.assertIsNone(result.cue)
        self.assertEqual(result.reason, "signal_quality_gate_closed")
