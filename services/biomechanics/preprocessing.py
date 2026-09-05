"""Reproducible, non-clinical preprocessing for versioned IMU transport data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

REQUIRED_ROLES = ("thigh", "shank", "foot")
AXES = ("ax", "ay", "az", "gx", "gy", "gz")


@dataclass(frozen=True, slots=True)
class PreprocessingResult:
    allowed: bool
    reasons: tuple[str, ...]
    sample_rate_hz: float
    frames: tuple[dict[str, Any], ...]
    parameters: dict[str, Any]


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def preprocess_transport_events(
    events: list[dict[str, Any]],
    *,
    signal_quality: dict[str, Any],
    target_rate_hz: float = 20.0,
    filter_window_samples: int = 3,
) -> PreprocessingResult:
    """Validate timestamps and linearly resample the three raw streams.

    This deliberately stops before fusion, angle estimation, segmentation and
    scoring. Those stages require an approved device protocol and calibration
    method; inventing either would be unsafe.
    """
    if target_rate_hz <= 0:
        raise ValueError("target_rate_hz must be positive")
    if filter_window_samples < 1 or filter_window_samples % 2 == 0:
        raise ValueError("filter_window_samples must be a positive odd number")
    parameters = {
        "target_rate_hz": target_rate_hz,
        "filter_kind": "centered_moving_average",
        "filter_window_samples": filter_window_samples,
    }
    if not signal_quality.get("scoring_permitted", False):
        return PreprocessingResult(
            False, ("signal_quality_gate_closed",), target_rate_hz, (), parameters
        )

    streams: dict[str, list[tuple[datetime, dict[str, Any]]]] = {
        role: [] for role in REQUIRED_ROLES
    }
    try:
        for event in events:
            role = event.get("sensor_role")
            if role in streams:
                streams[role].append((_timestamp(event["timestamp_gateway"]), event))
    except (KeyError, TypeError, ValueError):
        return PreprocessingResult(
            False, ("invalid_gateway_timestamp",), target_rate_hz, (), parameters
        )
    if any(not stream for stream in streams.values()):
        return PreprocessingResult(
            False, ("missing_required_sensor_stream",), target_rate_hz, (), parameters
        )

    for stream in streams.values():
        stream.sort(key=lambda item: item[0])
    started_at = max(stream[0][0] for stream in streams.values())
    ended_at = min(stream[-1][0] for stream in streams.values())
    if ended_at <= started_at:
        return PreprocessingResult(
            False, ("no_common_sensor_time_window",), target_rate_hz, (), parameters
        )

    step_seconds = 1 / target_rate_hz
    frame_count = int((ended_at - started_at).total_seconds() / step_seconds) + 1
    resampled_frames = tuple(
        {
            "timestamp_gateway": (started_at.timestamp() + index * step_seconds),
            "sensors": {
                role: _interpolate(stream, started_at.timestamp() + index * step_seconds)
                for role, stream in streams.items()
            },
        }
        for index in range(frame_count)
    )
    return PreprocessingResult(
        True,
        (),
        target_rate_hz,
        filter_resampled_frames(resampled_frames, window_samples=filter_window_samples),
        parameters,
    )


def filter_resampled_frames(
    frames: tuple[dict[str, Any], ...], *, window_samples: int
) -> tuple[dict[str, Any], ...]:
    """Apply a bounded centered moving average without interpreting movement."""
    if window_samples < 1 or window_samples % 2 == 0:
        raise ValueError("window_samples must be a positive odd number")
    radius = window_samples // 2
    filtered: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        lower = max(0, index - radius)
        upper = min(len(frames), index + radius + 1)
        filtered.append(
            {
                "timestamp_gateway": frame["timestamp_gateway"],
                "sensors": {
                    role: {
                        axis: sum(source["sensors"][role][axis] for source in frames[lower:upper])
                        / (upper - lower)
                        for axis in AXES
                    }
                    for role in REQUIRED_ROLES
                },
            }
        )
    return tuple(filtered)


def _interpolate(
    stream: list[tuple[datetime, dict[str, Any]]], timestamp: float
) -> dict[str, float]:
    """Interpolate raw axes in a shared time base without interpreting them."""
    for index, (right_time, right) in enumerate(stream):
        right_timestamp = right_time.timestamp()
        if right_timestamp >= timestamp:
            if index == 0 or right_timestamp == timestamp:
                return {axis: float(right[axis]) for axis in AXES}
            left_time, left = stream[index - 1]
            left_timestamp = left_time.timestamp()
            fraction = (timestamp - left_timestamp) / (right_timestamp - left_timestamp)
            return {
                axis: float(left[axis]) + (float(right[axis]) - float(left[axis])) * fraction
                for axis in AXES
            }
    return {axis: float(stream[-1][1][axis]) for axis in AXES}
