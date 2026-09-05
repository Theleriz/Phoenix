import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from preprocessing import preprocess_transport_events


def event(role: str, timestamp: datetime, value: int) -> dict[str, object]:
    return {
        "sensor_role": role,
        "timestamp_gateway": timestamp.isoformat(),
        "ax": value,
        "ay": value,
        "az": value,
        "gx": value,
        "gy": value,
        "gz": value,
    }


class PreprocessingTests(unittest.TestCase):
    def test_quality_gate_blocks_low_or_invalid_stream(self) -> None:
        result = preprocess_transport_events([], signal_quality={"scoring_permitted": False})
        self.assertFalse(result.allowed)
        self.assertEqual(result.reasons, ("signal_quality_gate_closed",))

    def test_resamples_three_streams_on_a_common_time_base(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=50 * index), index)
            for role in ("thigh", "shank", "foot")
            for index in range(3)
        ]
        result = preprocess_transport_events(events, signal_quality={"scoring_permitted": True})
        self.assertTrue(result.allowed)
        self.assertEqual(len(result.frames), 3)
        self.assertEqual(result.frames[1]["sensors"]["shank"]["gy"], 1.0)
        self.assertEqual(result.parameters["filter_kind"], "centered_moving_average")
        self.assertEqual(result.frames[0]["sensors"]["thigh"]["ax"], 0.5)

    def test_requires_all_sensor_streams(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        result = preprocess_transport_events(
            [event("thigh", started, 0)], signal_quality={"scoring_permitted": True}
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reasons, ("missing_required_sensor_stream",))

    def test_filter_window_is_explicit_and_must_be_odd(self) -> None:
        with self.assertRaises(ValueError):
            preprocess_transport_events(
                [], signal_quality={"scoring_permitted": True}, filter_window_samples=2
            )
