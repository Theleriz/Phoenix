"""Deterministic, versioned patient-reported safety triage; never a diagnosis.

Classifies whether reported facts match a pre-approved trigger requiring
clinician review (YELLOW) or urgent action (RED). It never infers a medical
condition, never runs on IMU data, and an unapproved policy always withholds
a result rather than guessing a severity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SafetyLevel(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class SafetyAssessmentStatus(StrEnum):
    EVALUATED = "evaluated"
    WITHHELD = "withheld"


@dataclass(frozen=True, slots=True)
class SafetyRulePolicy:
    version: str
    clinically_approved: bool
    red_symptom_keys: frozenset[str]
    yellow_symptom_keys: frozenset[str]
    pain_increase_yellow_threshold: float | None

    @classmethod
    def from_configuration(cls, configuration: dict[str, Any]) -> SafetyRulePolicy:
        version = str(configuration.get("version", ""))
        if not version:
            raise ValueError("safety rule policy version is required")
        threshold = configuration.get("pain_increase_yellow_threshold")
        red_keys = frozenset(str(key) for key in configuration.get("red_symptom_keys", []))
        yellow_keys = frozenset(str(key) for key in configuration.get("yellow_symptom_keys", []))
        if red_keys & yellow_keys:
            raise ValueError("a symptom key cannot be both a red and yellow trigger")
        return cls(
            version=version,
            clinically_approved=configuration.get("approval_state") == "clinically_approved",
            red_symptom_keys=red_keys,
            yellow_symptom_keys=yellow_keys,
            pain_increase_yellow_threshold=(
                float(threshold) if threshold is not None else None
            ),
        )


@dataclass(frozen=True, slots=True)
class SafetyAssessment:
    status: SafetyAssessmentStatus
    level: SafetyLevel | None
    reasons: tuple[str, ...]
    policy_version: str


def evaluate_safety_rules(
    *,
    policy: SafetyRulePolicy,
    reported_symptoms: frozenset[str],
    pain_before: float | None = None,
    pain_after: float | None = None,
) -> SafetyAssessment:
    """Evaluate one post-session symptom check against an organization's policy.

    RED wins over YELLOW when both trigger. GREEN means no configured trigger
    matched, not that the patient is clinically fine.
    """
    if not policy.clinically_approved:
        return SafetyAssessment(SafetyAssessmentStatus.WITHHELD, None, (), policy.version)

    reasons: list[str] = []
    red_hits = reported_symptoms & policy.red_symptom_keys
    reasons.extend(f"red_symptom:{key}" for key in sorted(red_hits))

    yellow_hits = reported_symptoms & policy.yellow_symptom_keys
    reasons.extend(f"yellow_symptom:{key}" for key in sorted(yellow_hits))

    unconfigured = reported_symptoms - policy.red_symptom_keys - policy.yellow_symptom_keys
    reasons.extend(f"unconfigured_symptom:{key}" for key in sorted(unconfigured))

    if (
        policy.pain_increase_yellow_threshold is not None
        and pain_before is not None
        and pain_after is not None
        and (pain_after - pain_before) >= policy.pain_increase_yellow_threshold
    ):
        reasons.append("pain_increase_at_or_above_threshold")

    if red_hits:
        level = SafetyLevel.RED
    elif reasons:
        level = SafetyLevel.YELLOW
    else:
        level = SafetyLevel.GREEN

    return SafetyAssessment(SafetyAssessmentStatus.EVALUATED, level, tuple(reasons), policy.version)
