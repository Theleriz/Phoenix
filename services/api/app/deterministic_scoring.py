"""Safe versioned scoring gate for clinically approved deterministic formulas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ScoreStatus(StrEnum):
    CALCULATED = "calculated"
    WITHHELD = "withheld"


@dataclass(frozen=True, slots=True)
class ScorePolicy:
    version: str
    clinically_approved: bool
    weights: dict[str, float]

    @classmethod
    def from_configuration(cls, configuration: dict[str, Any]) -> ScorePolicy:
        raw_weights = configuration.get("weights", {})
        weights = {str(name): float(weight) for name, weight in raw_weights.items()}
        policy = cls(
            version=str(configuration.get("version", "")),
            clinically_approved=configuration.get("approval_state") == "clinically_approved",
            weights=weights,
        )
        if not policy.version:
            raise ValueError("score policy version is required")
        if policy.weights and abs(sum(policy.weights.values()) - 1.0) > 1e-9:
            raise ValueError("score weights must sum to one")
        if any(weight < 0 for weight in policy.weights.values()):
            raise ValueError("score weights cannot be negative")
        return policy


@dataclass(frozen=True, slots=True)
class DeterministicScore:
    status: ScoreStatus
    value: float | None
    policy_version: str
    components: dict[str, float]
    reason: str
    ml_component_included: bool = False


def calculate_deterministic_score(
    *,
    policy: ScorePolicy,
    components: dict[str, float],
    signal_quality: dict[str, Any],
) -> DeterministicScore:
    """Calculate only an explicitly approved, fully specified weighted score."""
    if not signal_quality.get("scoring_permitted", False):
        return DeterministicScore(
            ScoreStatus.WITHHELD,
            None,
            policy.version,
            {},
            "signal_quality_gate_closed",
        )
    if not policy.clinically_approved:
        return DeterministicScore(
            ScoreStatus.WITHHELD,
            None,
            policy.version,
            {},
            "formula_not_clinically_approved",
        )
    if not policy.weights or set(components) != set(policy.weights):
        return DeterministicScore(
            ScoreStatus.WITHHELD,
            None,
            policy.version,
            {},
            "required_components_missing_or_unexpected",
        )
    if any(not 0.0 <= value <= 1.0 for value in components.values()):
        raise ValueError("score components must be normalized to the range zero to one")
    value = round(sum(components[name] * weight for name, weight in policy.weights.items()), 12)
    return DeterministicScore(
        ScoreStatus.CALCULATED,
        value,
        policy.version,
        dict(components),
        "calculated",
    )
