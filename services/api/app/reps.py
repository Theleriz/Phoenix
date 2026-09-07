"""Deterministic repetition segmentation on preprocessed IMU frames.

Non-clinical. For a heel slide the knee flexes then extends once per rep; the
flexion proxy here is the shank-vs-thigh pitch difference (device orientation,
degrees). A rep is one excursion past a flexion threshold and back past an
extension threshold (hysteresis + a minimum duration). This is the *primary*
rep signal returned to the patient app. A trained model's rep boundaries, when
a checkpoint is present, run in the shadow branch for comparison only and
never replace this until clinically approved.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

FLEXION_PROXY = "shank_minus_thigh_ori_pitch_deg"

# Engineering defaults for the dev scaffold, not clinical thresholds.
ENTER_FLEXION_DEG = 18.0
EXIT_FLEXION_DEG = 7.0
MIN_REP_FRAMES = 5  # ~250 ms at 20 Hz: rejects jitter blips
MIN_FRAMES = 12
RECENT_COMPLETION_FRAMES = 6  # a rep counts as "just completed" if it ended within this many frames


@dataclass(frozen=True, slots=True)
class RepReport:
    count: int
    completion_timestamps: tuple[float, ...]
    just_completed: bool
    last_completed_at: float | None
    amplitude_degrees: float
    proxy: str
    reason: str | None


def _flexion_signal(frames: list[dict[str, Any]]) -> list[float]:
    signal: list[float] = []
    for frame in frames:
        sensors = frame["sensors"]
        signal.append(float(sensors["shank"]["ori_pitch"]) - float(sensors["thigh"]["ori_pitch"]))
    return signal


def count_repetitions(
    frames: list[dict[str, Any]],
    *,
    enter_deg: float = ENTER_FLEXION_DEG,
    exit_deg: float = EXIT_FLEXION_DEG,
    min_rep_frames: int = MIN_REP_FRAMES,
) -> RepReport:
    """Count flexion/extension cycles in a window of preprocessed frames."""
    frames = list(frames)
    if len(frames) < MIN_FRAMES:
        return RepReport(0, (), False, None, 0.0, FLEXION_PROXY, "insufficient_frames")

    raw = _flexion_signal(frames)
    baseline = statistics.median(raw)
    # Orient the signal so flexion (the larger excursion from rest) is positive.
    sign = 1.0 if (max(raw) - baseline) >= (baseline - min(raw)) else -1.0
    magnitude = [sign * (value - baseline) for value in raw]
    amplitude = max(magnitude)

    completion_indices: list[int] = []
    state = "rest"
    segment_start = 0
    segment_peak = 0.0
    for index, value in enumerate(magnitude):
        if state == "rest":
            if value >= enter_deg:
                state = "flexed"
                segment_start = index
                segment_peak = value
        else:
            segment_peak = max(segment_peak, value)
            if value <= exit_deg:
                long_enough = index - segment_start >= min_rep_frames
                if long_enough and segment_peak >= enter_deg:
                    completion_indices.append(index)
                state = "rest"

    completion_timestamps = tuple(
        float(frames[i]["timestamp_gateway"]) for i in completion_indices
    )
    just_completed = bool(completion_indices) and (
        len(frames) - completion_indices[-1] <= RECENT_COMPLETION_FRAMES
    )
    return RepReport(
        count=len(completion_indices),
        completion_timestamps=completion_timestamps,
        just_completed=just_completed,
        last_completed_at=completion_timestamps[-1] if completion_timestamps else None,
        amplitude_degrees=round(amplitude, 2),
        proxy=FLEXION_PROXY,
        reason=None if amplitude >= enter_deg else "no_flexion_detected",
    )
