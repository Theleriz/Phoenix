import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.preprocessing import CHANNELS, preprocess_transport_events


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
        "orientation_euler_degrees": [value, value, value],
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

    def test_carries_all_nine_channels_and_frame_flags(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=50 * index), index)
            for role in ("thigh", "shank", "foot")
            for index in range(3)
        ]
        result = preprocess_transport_events(events, signal_quality={"scoring_permitted": True})
        self.assertEqual(tuple(result.parameters["channels"]), CHANNELS)
        self.assertEqual(len(CHANNELS), 9)
        thigh = result.frames[0]["sensors"]["thigh"]
        self.assertEqual(set(thigh), set(CHANNELS))
        flags = result.frames[0]["flags"]
        self.assertFalse(flags["interpolated_over_gap"])
        self.assertFalse(flags["near_full_scale"])

    def test_flags_frames_reconstructed_across_a_dropout(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        gaps_ms = (0, 100, 700, 800)  # 600 ms hole between the 2nd and 3rd sample
        events = [
            event(role, started + timedelta(milliseconds=offset), index)
            for role in ("thigh", "shank", "foot")
            for index, offset in enumerate(gaps_ms)
        ]
        result = preprocess_transport_events(events, signal_quality={"scoring_permitted": True})
        self.assertTrue(result.allowed)
        self.assertTrue(any(frame["flags"]["interpolated_over_gap"] for frame in result.frames))

    def test_near_full_scale_is_flagged(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = []
        for role in ("thigh", "shank", "foot"):
            for index in range(3):
                item = event(role, started + timedelta(milliseconds=50 * index), 0)
                item["gx"] = 32500
                events.append(item)
        result = preprocess_transport_events(events, signal_quality={"scoring_permitted": True})
        self.assertTrue(any(frame["flags"]["near_full_scale"] for frame in result.frames))

    def test_requires_all_sensor_streams(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        result = preprocess_transport_events(
            [event("thigh", started, 0)], signal_quality={"scoring_permitted": True}
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reasons, ("missing_required_sensor_stream",))

    def test_events_without_orientation_are_dropped_from_their_stream(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = []
        for role in ("thigh", "shank", "foot"):
            for index in range(3):
                item = event(role, started + timedelta(milliseconds=50 * index), index)
                if role == "foot":
                    del item["orientation_euler_degrees"]
                events.append(item)
        result = preprocess_transport_events(events, signal_quality={"scoring_permitted": True})
        self.assertFalse(result.allowed)
        self.assertEqual(result.reasons, ("missing_required_sensor_stream",))
        self.assertEqual(result.parameters["dropped_events_missing_orientation"], 3)

    def test_filter_window_is_explicit_and_must_be_odd(self) -> None:
        with self.assertRaises(ValueError):
            preprocess_transport_events(
                [], signal_quality={"scoring_permitted": True}, filter_window_samples=2
            )
