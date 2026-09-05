"""Versioned deterministic cue gate; never invents clinical exercise advice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class CuePolicy:
    rule_version: str
    clinically_approved: bool
    allowed_cues: frozenset[str]
    debounce_observations: int
    cooldown_seconds: float

    @classmethod
    def from_configuration(cls, configuration: dict[str, Any]) -> CuePolicy:
        policy = cls(
            rule_version=str(configuration.get("rule_version", "")),
            clinically_approved=configuration.get("approval_state") == "clinically_approved",
            allowed_cues=frozenset(configuration.get("live_feedback_whitelist", [])),
            debounce_observations=int(configuration.get("debounce_observations", 1)),
            cooldown_seconds=float(configuration.get("cooldown_seconds", 0)),
        )
        if not policy.rule_version:
            raise ValueError("rule_version is required")
        if policy.debounce_observations < 1 or policy.cooldown_seconds < 0:
            raise ValueError("invalid debounce or cooldown configuration")
        return policy


@dataclass(slots=True)
class CueState:
    active_cue: str | None = None
    consecutive_observations: int = 0
    last_emitted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CueDecision:
    cue: str | None
    reason: str
    rule_version: str


def decide_cue(
    *,
    candidate_cue: str | None,
    signal_quality: dict[str, Any],
    policy: CuePolicy,
    state: CueState,
    observed_at: datetime,
) -> CueDecision:
    """Emit at most one approved deterministic cue after debounce and cooldown."""
    if not signal_quality.get("scoring_permitted", False):
        state.active_cue = None
        state.consecutive_observations = 0
        return CueDecision(None, "signal_quality_gate_closed", policy.rule_version)
    if not policy.clinically_approved:
        return CueDecision(None, "rule_not_clinically_approved", policy.rule_version)
    if candidate_cue is None:
        state.active_cue = None
        state.consecutive_observations = 0
        return CueDecision(None, "no_candidate", policy.rule_version)
    if candidate_cue not in policy.allowed_cues:
        return CueDecision(None, "cue_not_whitelisted", policy.rule_version)
    if candidate_cue == state.active_cue:
        state.consecutive_observations += 1
    else:
        state.active_cue = candidate_cue
        state.consecutive_observations = 1
    if state.consecutive_observations < policy.debounce_observations:
        return CueDecision(None, "debounce_pending", policy.rule_version)
    if state.last_emitted_at is not None:
        elapsed = observed_at - state.last_emitted_at
        if elapsed < timedelta(seconds=policy.cooldown_seconds):
            return CueDecision(None, "cooldown_active", policy.rule_version)
    state.last_emitted_at = observed_at
    return CueDecision(candidate_cue, "emitted", policy.rule_version)
