"""Explicitly non-clinical data used solely by the local development screens."""

from __future__ import annotations

from copy import deepcopy

_DEMO_SNAPSHOT = {
    "organization": {"id": "org-demo", "name": "PHOENIX Demo Clinic"},
    "patient": {"id": "patient-demo", "display_name": "Демо-пациент", "post_op_day": 14},
    "clinician": {"id": "clinician-demo", "display_name": "Демо-врач"},
    "protocol": {"id": "protocol-demo", "name": "Synthetic replay only"},
    "replay_session": {
        "id": "synthetic-session-v1",
        "origin": "synthetic",
        "validation_status": "synthetic",
        "sensor_roles": ["thigh", "shank", "foot"],
        "frame_count": 15,
    },
    "safety_notice": (
        "Демо-данные не являются измерением пациента и не используются для score, alert "
        "или клинических решений."
    ),
}


def demo_snapshot() -> dict[str, object]:
    """Return a fresh copy so a caller cannot mutate the server's fixture."""
    return deepcopy(_DEMO_SNAPSHOT)
