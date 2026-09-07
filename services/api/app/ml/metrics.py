"""Deterministic, explainable movement features from preprocessed frames.

Stage 8 of IMPLEMENTATION_PLAN.md keeps ROM / repetition count / tempo / hold
as non-ML metrics computed from the same frames the model sees, so the
deterministic and ML branches stay independent and separately auditable.

NOT IMPLEMENTED yet: these need the calibrated relative thigh/shank
orientation (``app.orientation.calibrated_relative_orientation``) and an
approved repetition-segmentation method. This module is only the seam.
"""

from __future__ import annotations

from typing import Any

PENDING_FEATURES = (
    "knee_flexion_extension_angle",
    "rom_per_repetition",
    "valid_incomplete_total_repetitions",
    "flexion_extension_tempo",
    "hold_duration",
    "active_paused_duration",
    "variation_between_repetitions",
)


def deterministic_features(
    frames: list[dict[str, Any]], *, calibration: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Placeholder: returns a stable 'not implemented' report, never fake numbers."""
    return {
        "status": "not_implemented",
        "frame_count": len(frames),
        "has_calibration": calibration is not None,
        "available": [],
        "pending": list(PENDING_FEATURES),
        "requires": [
            "calibrated_relative_thigh_shank_orientation",
            "approved_repetition_segmentation",
        ],
    }
