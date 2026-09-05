import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from shadow import ShadowStatus, shadow_infer


class ShadowInferenceTests(unittest.TestCase):
    def test_abstains_when_signal_quality_is_closed(self) -> None:
        prediction = shadow_infer(
            signal_quality={"scoring_permitted": False},
            model_version="shadow-v1",
            feature_versions=["preprocessing-v1"],
        )
        self.assertEqual(prediction.status, ShadowStatus.ABSTAINED)
        self.assertEqual(prediction.reason, "signal_quality_gate_closed")
        self.assertFalse(prediction.affects_score)

    def test_abstains_without_a_validated_model(self) -> None:
        prediction = shadow_infer(
            signal_quality={"scoring_permitted": True},
            model_version="shadow-v1",
            feature_versions=["preprocessing-v1", "orientation-v1"],
        )
        self.assertEqual(prediction.reason, "no_validated_local_model_available")
        self.assertTrue(prediction.shadow_mode)
        self.assertFalse(prediction.affects_feedback)
