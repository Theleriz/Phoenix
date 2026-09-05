"""Signed-token and role helpers for the local development API."""

from __future__ import annotations

import hashlib
import hmac
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta

PRIVILEGED_PATIENT_VIEW_ROLES = frozenset(
    {"clinician", "rehabilitologist", "organization_admin", "technical_admin"}
)


def issue_token(*, user_id: str, organization_id: str, secret: str) -> str:
    payload = {
        "exp": int((datetime.now(UTC) + timedelta(hours=8)).timestamp()),
        "organization_id": organization_id,
        "user_id": user_id,
    }
    encoded = urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).rstrip(b"=")
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def verify_token(token: str, *, secret: str) -> dict[str, object] | None:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
        padding = "=" * (-len(supplied_signature) % 4)
        if not hmac.compare_digest(expected, urlsafe_b64decode(supplied_signature + padding)):
            return None
        payload = json.loads(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        return payload if int(payload["exp"]) > int(datetime.now(UTC).timestamp()) else None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def can_view_patient(*, roles: frozenset[str], patient_user_id: str | None, user_id: str) -> bool:
    return bool(roles & PRIVILEGED_PATIENT_VIEW_ROLES) or (
        "patient" in roles and patient_user_id == user_id
    )
