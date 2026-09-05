"""Framework-neutral contracts for the stage 5 protocol engine.

The contracts deliberately describe configuration and provenance.  They do not
contain clinical thresholds; those belong in an approved, versioned exercise
configuration.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

RESTRICTION_PRIORITY = (
    "individual_clinician",
    "clinic_or_surgeon_template",
    "phoenix_base_template",
)
EXERCISE_IDS = (
    "heel_slide",
    "short_arc_quad",
    "ankle_pumps",
    "straight_leg_raise",
    "prone_knee_bend",
)
REQUIRED_EXERCISE_FIELDS = (
    "required_sensors",
    "reference_video",
    "instructions",
    "primary_metrics",
    "secondary_metrics",
    "prescription_schema",
    "valid_repetition_definition",
    "stop_conditions",
    "live_feedback_whitelist",
    "scoring_formula",
    "limitations",
)


@dataclass(frozen=True)
class ExerciseConfig:
    """A serializable exercise definition, independent of the API/database."""

    id: str
    name: str
    recovery_phase: str | None
    patient_position: str | None
    configuration: Mapping[str, Any]

    def validate(self) -> list[str]:
        errors: list[str] = []
        missing = [key for key in REQUIRED_EXERCISE_FIELDS if key not in self.configuration]
        if missing:
            errors.append(f"missing configuration fields: {', '.join(missing)}")
        sensors = self.configuration.get("required_sensors")
        if not isinstance(sensors, list) or not sensors:
            errors.append("required_sensors must be a non-empty list")
        whitelist = self.configuration.get("live_feedback_whitelist")
        if not isinstance(whitelist, list):
            errors.append("live_feedback_whitelist must be a list")
        return errors


def merge_restrictions(
    *,
    base: Mapping[str, Any],
    clinic: Mapping[str, Any] | None = None,
    individual: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply restrictions from least to most specific, preserving provenance."""

    merged: dict[str, Any] = dict(base)
    sources: list[dict[str, Any]] = [{"source": "phoenix_base_template", "values": dict(base)}]
    for source_name, values in (
        ("clinic_or_surgeon_template", clinic),
        ("individual_clinician", individual),
    ):
        if values:
            merged.update(values)
            sources.append({"source": source_name, "values": dict(values)})
    merged["restriction_sources"] = sources
    return merged


def validate_prescription(configuration: Mapping[str, Any]) -> list[str]:
    """Validate safe data-shape constraints, without inventing clinical limits."""

    errors: list[str] = []
    for field in ("sets", "repetitions"):
        value = configuration.get(field)
        if value is not None and (not isinstance(value, int) or value < 1):
            errors.append(f"{field} must be a positive integer or null")
    rom = configuration.get("target_rom_degrees")
    if rom is not None and (not isinstance(rom, int | float) or not 0 <= rom <= 180):
        errors.append("target_rom_degrees must be between 0 and 180 or null")
    if configuration.get("approval_state", "draft") not in {"draft", "clinically_approved"}:
        errors.append("prescription approval_state must be draft or clinically_approved")
    return errors
