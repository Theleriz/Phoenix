import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.ml.inference import _run_limu_bert, run_shadow_inference
from app.ml.input import build_model_input, sliding_windows, to_limu_units
from app.ml.model import ModelBundle, ModelMeta
from app.preprocessing import CHANNELS, REQUIRED_ROLES, preprocess_transport_events

try:
    import torch  # noqa: F401

    _HAVE_TORCH = True
except ImportError:
    _HAVE_TORCH = False


def _event(role: str, moment: datetime, value: int) -> dict[str, object]:
    return {
        "sensor_role": role,
        "timestamp_gateway": moment.isoformat(),
        "ax": value, "ay": value, "az": value,
        "gx": value, "gy": value, "gz": value,
        "orientation_euler_degrees": [value, value, value],
    }


def _frames(samples: int = 12) -> list[dict[str, object]]:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    events = [
        _event(role, started + timedelta(milliseconds=100 * index), index)
        for role in ("thigh", "shank", "foot")
        for index in range(samples)
    ]
    result = preprocess_transport_events(
        events, signal_quality={"scoring_permitted": True}, filter_window_samples=1
    )
    assert result.allowed
    return list(result.frames)


class BuildModelInputTests(unittest.TestCase):
    def test_shape_order_and_physical_units(self) -> None:
        model_input = build_model_input(_frames())
        self.assertEqual(model_input.tensor.shape[1:], (3, 9))
        self.assertEqual(model_input.channels, CHANNELS)
        self.assertEqual(model_input.sensor_order, REQUIRED_ROLES)
        self.assertFalse(model_input.dropped)
        # Every raw channel == its sample index; converted to g with the
        # 16/32768 datasheet scale. The last resampled frame sits at the end of
        # the common window, i.e. raw ~= samples - 1.
        accel_g_per_lsb = 16.0 / 32768.0
        self.assertAlmostEqual(float(model_input.tensor[0, 0, 2]), 0.0)
        last_az_raw = float(model_input.tensor[-1, 0, 2]) / accel_g_per_lsb
        self.assertAlmostEqual(last_az_raw, 11.0, places=3)

    def test_empty_frames_marks_dropped(self) -> None:
        model_input = build_model_input([])
        self.assertTrue(model_input.dropped)
        self.assertEqual(model_input.tensor.shape, (0, 3, 9))

    def test_sliding_windows_shape(self) -> None:
        model_input = build_model_input(_frames(samples=30))
        windows = sliding_windows(model_input.tensor, window=10, stride=5)
        self.assertEqual(windows.shape[1:], (10, 3, 9))
        self.assertGreater(windows.shape[0], 1)

    def test_to_limu_units(self) -> None:
        tensor = np.ones((2, 4, 9), dtype=np.float32)
        out = to_limu_units(tensor)
        self.assertAlmostEqual(float(out[0, 0, 0]), 9.80665, places=4)  # accel g -> m/s^2
        self.assertAlmostEqual(float(out[0, 0, 3]), np.pi / 180.0, places=6)  # gyro deg/s -> rad/s
        self.assertEqual(float(out[0, 0, 6]), 1.0)  # orientation unchanged
        self.assertEqual(float(tensor[0, 0, 0]), 1.0)  # input not mutated


class LimuBertFusionTests(unittest.TestCase):
    def _bundle(self, hidden: int = 72) -> ModelBundle:
        meta = ModelMeta(
            model_version="test-limu",
            feature_versions=("v",),
            window_samples=120,
            rate_hz=20.0,
            channels=CHANNELS,
            sensor_order=REQUIRED_ROLES,
            framework="limu_bert",
            input_layout="per_sensor_limu6",
            normalization={"kind": "limu"},
        )

        def fake_runner(batch: np.ndarray) -> np.ndarray:
            # (N, W, 6) -> (N, W, hidden); assert only 6 channels reach the model
            assert batch.shape[-1] == 6, batch.shape
            return np.zeros((batch.shape[0], batch.shape[1], hidden), dtype=np.float32)

        return ModelBundle(meta=meta, weights_path=Path("x"), runner=fake_runner)

    def test_per_sensor_loop_and_fusion_shape(self) -> None:
        windows = np.ones((5, 120, 3, 9), dtype=np.float32)
        embedding, extra = _run_limu_bert(self._bundle(hidden=72), windows)
        self.assertEqual(len(embedding), 72 * 3)
        self.assertEqual(extra["embedding_dim"], 216)
        self.assertEqual(extra["per_sensor_hidden"], 72)
        self.assertEqual(extra["fusion"], "per_sensor_meanpool_concat")

    @unittest.skipUnless(_HAVE_TORCH, "torch not installed")
    def test_vendored_encoder_loads_its_own_state_dict(self) -> None:
        import tempfile

        import torch
        from app.ml.limu_bert.config import LimuBertConfig
        from app.ml.limu_bert.encoder import Transformer, load_encoder

        cfg = LimuBertConfig(feature_num=6, seq_len=120)
        model = Transformer(cfg)
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as handle:
            torch.save({f"transformer.{k}": v for k, v in model.state_dict().items()}, handle.name)
            path = Path(handle.name)
        try:
            encoder, report = load_encoder(path, cfg)
            self.assertEqual(report["missing"], [])
            self.assertEqual(report["matched"], report["encoder_params"])
            out = encoder(torch.zeros(2, 120, 6))
            self.assertEqual(tuple(out.shape), (2, 120, 72))
        finally:
            path.unlink(missing_ok=True)


class RunShadowInferenceTests(unittest.TestCase):
    def test_abstains_without_a_checkpoint(self) -> None:
        prediction = run_shadow_inference(_frames(), {"scoring_permitted": True})
        self.assertEqual(prediction["status"], "abstained")
        self.assertEqual(prediction["reason"], "no_validated_local_model_available")
        self.assertTrue(prediction["shadow_mode"])
        self.assertFalse(prediction["affects_score"])
        self.assertFalse(prediction["affects_feedback"])
        self.assertGreater(prediction["input_frames"], 0)
        self.assertEqual(prediction["input_shape"][1:], [3, 9])

    def test_abstains_when_quality_gate_closed(self) -> None:
        prediction = run_shadow_inference([], {"scoring_permitted": False})
        self.assertEqual(prediction["status"], "abstained")
        self.assertEqual(prediction["reason"], "signal_quality_gate_closed")
        self.assertTrue(prediction["input_dropped"])


if __name__ == "__main__":
    unittest.main()
