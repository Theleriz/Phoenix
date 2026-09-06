"""Versioned shadow-inference gate; predictions never drive patient output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class ShadowStatus(StrEnum):
    PREDICTED = "predicted"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True)
class ShadowPrediction:
    status: ShadowStatus
    model_version: str
    label: str | None
    confidence: float
    feature_versions: tuple[str, ...]
    reason: str | None
    shadow_mode: bool = True
    affects_score: bool = False
    affects_feedback: bool = False

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


def shadow_infer(
    *,
    signal_quality: dict[str, Any],
    model_version: str,
    feature_versions: list[str],
    model_available: bool = False,
) -> ShadowPrediction:
    """Apply the pre-inference gates.

    Returns ``ABSTAINED`` (with a machine-readable ``reason``) when the signal
    quality gate is closed or no validated model is loaded. Returns
    ``PREDICTED`` only to signal that the gates are open -- the caller
    (``ml.inference``) then runs the model and fills in ``label`` /
    ``confidence`` / embedding. Either way the result stays ``shadow_mode`` and
    never affects score or feedback until clinical approval.
    """
    if not model_version:
        raise ValueError("model_version is required")
    if not feature_versions:
        raise ValueError("at least one feature version is required")
    features = tuple(feature_versions)
    if not signal_quality.get("scoring_permitted", False):
        return ShadowPrediction(
            ShadowStatus.ABSTAINED,
            model_version,
            None,
            0.0,
            features,
            "signal_quality_gate_closed",
        )
    if not model_available:
        return ShadowPrediction(
            ShadowStatus.ABSTAINED,
            model_version,
            None,
            0.0,
            features,
            "no_validated_local_model_available",
        )
    return ShadowPrediction(
        ShadowStatus.PREDICTED,
        model_version,
        None,
        0.0,
        features,
        None,
    )
