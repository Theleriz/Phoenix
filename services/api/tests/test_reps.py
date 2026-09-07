import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.reps import count_repetitions


def _frame(ts: float, shank_pitch: float, thigh_pitch: float = 0.0) -> dict[str, object]:
    return {
        "timestamp_gateway": ts,
        "sensors": {
            "thigh": {"ori_pitch": thigh_pitch},
            "shank": {"ori_pitch": shank_pitch},
            "foot": {"ori_pitch": 0.0},
        },
    }


def _cycles(
    n_reps: int, rest_frames: int = 20, ramp_frames: int = 10, amplitude: float = 40.0
) -> list[dict[str, object]]:
    """Realistic rest-heavy reps: a flat rest, then a symmetric flex pulse that
    ends back at rest. Last frame of the last rep is at rest."""
    frames: list[dict[str, object]] = []
    ts = 0
    for _ in range(n_reps):
        for _ in range(rest_frames):
            frames.append(_frame(ts * 0.05, 0.0))
            ts += 1
        for k in range(ramp_frames):  # rest -> peak
            frames.append(_frame(ts * 0.05, amplitude * (k + 1) / ramp_frames))
            ts += 1
        for k in range(ramp_frames):  # peak -> rest
            frames.append(_frame(ts * 0.05, amplitude * (ramp_frames - 1 - k) / ramp_frames))
            ts += 1
    return frames


class RepCountTests(unittest.TestCase):
    def test_counts_clean_cycles(self) -> None:
        report = count_repetitions(_cycles(5))
        self.assertEqual(report.count, 5)
        self.assertEqual(report.proxy, "shank_minus_thigh_ori_pitch_deg")
        self.assertGreater(report.amplitude_degrees, 30)
        self.assertIsNone(report.reason)

    def test_just_completed_fires_at_end_of_a_rep(self) -> None:
        frames = _cycles(3)
        report = count_repetitions(frames)
        # the sinusoid returns to ~0 exactly at the last frame -> a completion
        self.assertEqual(report.count, 3)
        self.assertTrue(report.just_completed)
        self.assertIsNotNone(report.last_completed_at)

    def test_just_completed_false_mid_flexion(self) -> None:
        frames = _cycles(3)
        # cut mid-way up the 3rd rep's flex (past rest, before the descent)
        cut = len(frames) - 12
        report = count_repetitions(frames[:cut])
        self.assertEqual(report.count, 2)
        self.assertFalse(report.just_completed)

    def test_hysteresis_ignores_small_wobble(self) -> None:
        frames = [_frame(i * 0.05, 5.0 * math.sin(i)) for i in range(200)]
        report = count_repetitions(frames)
        self.assertEqual(report.count, 0)
        self.assertEqual(report.reason, "no_flexion_detected")

    def test_short_window_is_insufficient(self) -> None:
        report = count_repetitions(_cycles(1)[:8])
        self.assertEqual(report.count, 0)
        self.assertEqual(report.reason, "insufficient_frames")


if __name__ == "__main__":
    unittest.main()
