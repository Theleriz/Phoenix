import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.signal_quality import SignalQualityLevel, evaluate_signal_quality


def event(role: str, at: datetime, sequence: int, **overrides: object) -> dict[str, object]:
    return {
        "sensor_role": role,
        "timestamp_gateway": at.isoformat(),
        "sequence_number": sequence,
        "ax": 0,
        "ay": 0,
        "az": 16_384,
        "gx": 0,
        "gy": 0,
        "gz": 0,
        **overrides,
    }


class SignalQualityTests(unittest.TestCase):
    def test_marks_complete_synchronised_calibration_stream_high(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=50 * index), index)
            for role in ("thigh", "shank", "foot")
            for index in range(61)
        ]
        report = evaluate_signal_quality(events)
        self.assertEqual(report.level, SignalQualityLevel.HIGH)
        self.assertEqual(report.reasons, ())

    def test_confirmed_hardware_10hz_stream_is_not_downgraded_by_sample_rate(self) -> None:
        """WT901BLE68 on its 10 Hz firmware setting must not trip the sample-rate gate.

        Real capture on 2026-09-05 measured ~10-12 Hz per sensor
        (docs/imu/current-script-audit.md); MIN_SAMPLE_RATE_HZ must stay at or
        below that observed minimum.
        """
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=100 * index), index)
            for role in ("thigh", "shank", "foot")
            for index in range(31)
        ]
        report = evaluate_signal_quality(events)
        self.assertNotIn("insufficient_sample_rate", report.reasons)
        self.assertEqual(report.level, SignalQualityLevel.HIGH)

    def test_confirmed_hardware_rest_noise_does_not_trip_the_motion_gate(self) -> None:
        """A real (stationary) WT901BLE68 capture on 2026-09-05 measured gx=700 at rest.

        MAX_STATIC_GYROSCOPE_RAW's prior limit of 100 was only ever validated
        against synthetic frames (always exactly zero at rest) and flagged
        every real hardware calibration attempt as movement.
        """
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=50 * index), index, gx=700, gy=135, gz=167)
            for role in ("thigh", "shank", "foot")
            for index in range(61)
        ]
        report = evaluate_signal_quality(events)
        self.assertNotIn("static_calibration_motion_detected", report.reasons)
        self.assertEqual(report.level, SignalQualityLevel.HIGH)

    def test_marks_missing_sensor_invalid(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        report = evaluate_signal_quality([event("thigh", started, 0)])
        self.assertEqual(report.level, SignalQualityLevel.INVALID)
        self.assertIn("missing_sensor_roles:foot,shank", report.reasons)

    def test_duplicate_timestamps_do_not_crash_the_timestamp_parse(self) -> None:
        """Two packets for one role sharing a host timestamp must not be
        misreported as ``invalid_gateway_timestamp`` (a tie used to fall through
        to comparing the event dicts, raising TypeError)."""
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = []
        for role in ("thigh", "shank", "foot"):
            for index in range(61):
                # every 5th sample duplicates the previous timestamp
                moment = started + timedelta(milliseconds=50 * (index - index % 5))
                events.append(event(role, moment, index))
        report = evaluate_signal_quality(events)
        self.assertNotIn("invalid_gateway_timestamp", report.reasons)

    def test_short_calibration_and_clipping_prevent_valid_signal(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=50), 0, gx=32_700)
            for role in ("thigh", "shank", "foot")
        ]
        report = evaluate_signal_quality(events)
        self.assertEqual(report.level, SignalQualityLevel.INVALID)
        self.assertIn("static_calibration_window_too_short", report.reasons)
        self.assertIn("sensor_clipping_detected", report.reasons)

    def test_sync_skew_is_medium_after_valid_calibration(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=50 * index), index)
            for role in ("thigh", "shank")
            for index in range(61)
        ]
        events.extend(
            event("foot", started + timedelta(milliseconds=50 * index + 300), index)
            for index in range(61)
        )
        report = evaluate_signal_quality(events)
        self.assertEqual(report.level, SignalQualityLevel.MEDIUM)
        self.assertIn("sensor_synchronization_out_of_range", report.reasons)

    def test_motion_during_static_calibration_is_low(self) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        events = [
            event(role, started + timedelta(milliseconds=50 * index), index, gy=2001)
            for role in ("thigh", "shank", "foot")
            for index in range(61)
        ]
        report = evaluate_signal_quality(events)
        self.assertEqual(report.level, SignalQualityLevel.LOW)
        self.assertIn("static_calibration_motion_detected", report.reasons)
