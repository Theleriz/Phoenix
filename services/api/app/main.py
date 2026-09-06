"""HTTP entry point for the local PHOENIX development environment."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.types.json import Json
from pydantic import BaseModel, Field, field_validator

from .demo import demo_snapshot
from .ml import run_shadow_inference
from .preprocessing import preprocess_transport_events
from .safety_rules import SafetyRulePolicy, evaluate_safety_rules
from .security import can_view_patient, issue_token, verify_token
from .signal_quality import evaluate_signal_quality

app = FastAPI(title="PHOENIX API", version="0.1.0", docs_url="/docs")

# A patient-reported symptom key: lowercase snake_case, matching the shape of the
# keys an org configures in its safety_rule_policies (e.g. "chest_pain").
_SYMPTOM_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_REPORTED_SYMPTOMS = 32
bearer = HTTPBearer()
INVITATION_ADMIN_ROLES = frozenset({"organization_admin", "technical_admin"})


class GatewayStreams:
    """In-process development fan-out; production needs a durable broker."""

    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = {}

    async def connect(
        self, session_id: str, client: WebSocket, *, subprotocol: str | None = None
    ) -> None:
        # Per the WebSocket spec, a client that offers Sec-WebSocket-Protocol
        # values requires the server to echo back one of them, or browsers
        # abort the connection even after a 101 handshake. `accept()` sends no
        # such header unless told to.
        await client.accept(subprotocol=subprotocol)
        self._clients.setdefault(session_id, set()).add(client)

    def disconnect(self, session_id: str, client: WebSocket) -> None:
        clients = self._clients.get(session_id)
        if clients is not None:
            clients.discard(client)
            if not clients:
                self._clients.pop(session_id, None)

    async def publish(self, session_id: str, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for client in self._clients.get(session_id, set()).copy():
            try:
                await client.send_json(event)
            except (RuntimeError, WebSocketDisconnect):
                stale.append(client)
        for client in stale:
            self.disconnect(session_id, client)


gateway_streams = GatewayStreams()


class LoginRequest(BaseModel):
    email: str
    password: str
    organization_id: str


class InvitationRequest(BaseModel):
    email: str
    role: str
    expires_in_hours: int = Field(default=72, ge=1, le=168)


class InvitationAcceptance(BaseModel):
    token: str
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=256)


class GatewayIMUPacket(BaseModel):
    """Version-one raw transport contract; fields have no clinical meaning."""

    session_id: str = Field(min_length=1, max_length=200)
    device_id: str = Field(min_length=1, max_length=200)
    sensor_role: str = Field(pattern="^(thigh|shank|foot)$")
    timestamp_device: float | None = None
    timestamp_gateway: datetime
    sequence_number: int = Field(ge=0)
    ax: int
    ay: int
    az: int
    gx: int
    gy: int
    gz: int
    orientation_euler_degrees: tuple[float, float, float] | None = None
    battery: int | None = Field(default=None, ge=0, le=100)
    origin: str = Field(pattern="^(synthetic|hardware)$")
    validation_status: str = Field(min_length=1, max_length=100)
    adapter_version: str = Field(min_length=1, max_length=100)


def database_url() -> str:
    return os.environ["DATABASE_URL"]


def auth_secret() -> str:
    return os.environ["API_AUTH_SECRET"]


def gateway_token_is_valid(token: str) -> bool:
    expected = os.environ.get("PHOENIX_GATEWAY_TOKEN")
    return bool(expected) and secrets.compare_digest(token, expected)


def ml_force_inference_enabled() -> bool:
    """Development-only: run preprocessing + shadow inference even when the
    signal-quality gate is closed.

    Real WT901BLE68 captures currently land LOW (no stay-still calibration hold
    in the recording), which would otherwise skip the ML branch entirely and
    make an end-to-end integration test impossible. When this is on, the branch
    runs against a copy of the quality report with ``scoring_permitted`` forced
    true and ``gate_overridden`` set; the persisted ``signal_quality`` row and
    the response's ``signal_quality`` field still carry the real, unmodified
    verdict. Never enable in production -- shadow predictions stay shadow-mode
    regardless, but the gate is a safety control.
    """
    return os.environ.get("PHOENIX_ML_FORCE_INFERENCE") == "1"


def current_identity(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict[str, object]:
    payload = verify_token(credentials.credentials, secret=auth_secret())
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = str(payload["user_id"])
    organization_id = str(payload["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT r.name FROM memberships m
               JOIN users u ON u.id = m.user_id
               JOIN roles r ON r.id = m.role_id
               WHERE m.user_id = %s AND m.organization_id = %s AND u.is_active""",
            (user_id, organization_id),
        )
        roles = frozenset(row[0] for row in cursor.fetchall())
    if not roles:
        raise HTTPException(status_code=401, detail="Inactive or unauthorized membership")
    return {"user_id": user_id, "organization_id": organization_id, "roles": roles}


Identity = Annotated[dict[str, object], Depends(current_identity)]


def require_roles(identity: dict[str, object], permitted: frozenset[str]) -> None:
    if not frozenset(identity["roles"]) & permitted:
        raise HTTPException(status_code=403, detail="Insufficient role")


def _insert_audit(
    cursor: Any,
    *,
    identity: dict[str, object],
    event_type: str,
    subject_type: str,
    subject_id: str,
) -> None:
    """Append one audit row on an existing cursor so it shares the caller's transaction."""
    cursor.execute(
        """INSERT INTO audit_events
           (id, organization_id, actor_user_id, event_type, subject_type, subject_id)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            str(uuid4()),
            str(identity["organization_id"]),
            str(identity["user_id"]),
            event_type,
            subject_type,
            subject_id,
        ),
    )


@app.post("/api/v1/auth/login", tags=["identity"])
def login(request: LoginRequest) -> dict[str, str]:
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT u.id FROM users u
               JOIN memberships m ON m.user_id = u.id
               WHERE u.email = %s AND m.organization_id = %s AND u.is_active
                 AND u.password_hash = crypt(%s, u.password_hash)
               LIMIT 1""",
            (request.email, request.organization_id, request.password),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Invalid credentials or organization")
        identity = {"user_id": row[0], "organization_id": request.organization_id}
        _insert_audit(
            cursor, identity=identity, event_type="login", subject_type="user", subject_id=row[0]
        )
    return {"access_token": issue_token(**identity, secret=auth_secret()), "token_type": "bearer"}


@app.post("/api/v1/invitations", status_code=201, tags=["identity"])
def create_invitation(request: InvitationRequest, identity: Identity) -> dict[str, str]:
    require_roles(identity, INVITATION_ADMIN_ROLES)
    invitation_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invited_email = request.email.lower()
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM roles WHERE name = %s",
            (request.role,),
        )
        role = cursor.fetchone()
        if role is None:
            raise HTTPException(status_code=422, detail="Unknown role")
        # An invitation may onboard a new email or recover access for someone who
        # already belongs to this organization. It must never be usable to reset
        # the credentials of a user whose memberships are all in other tenants.
        cursor.execute(
            """SELECT 1 FROM users u
               WHERE u.email = %s
                 AND NOT EXISTS (
                     SELECT 1 FROM memberships m
                     WHERE m.user_id = u.id AND m.organization_id = %s
                 )""",
            (invited_email, str(identity["organization_id"])),
        )
        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="A user with this email already exists outside this organization",
            )
        cursor.execute(
            """INSERT INTO invitations
               (id, organization_id, email, role_id, token_hash, expires_at, created_by_user_id)
               VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP + (%s * INTERVAL '1 hour'), %s)""",
            (
                invitation_id,
                str(identity["organization_id"]),
                invited_email,
                role[0],
                token_hash,
                request.expires_in_hours,
                str(identity["user_id"]),
            ),
        )
        _insert_audit(
            cursor,
            identity=identity,
            event_type="invitation_created",
            subject_type="invitation",
            subject_id=invitation_id,
        )
    # The token is shown once for the development flow. Production must deliver it out of band.
    return {"invitation_id": invitation_id, "token": token}


@app.post("/api/v1/invitations/accept", tags=["identity"])
def accept_invitation(request: InvitationAcceptance) -> dict[str, str]:
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT i.id, i.organization_id, i.email, i.role_id
               FROM invitations i
               WHERE i.token_hash = %s AND i.accepted_at IS NULL
                 AND i.expires_at > CURRENT_TIMESTAMP
               FOR UPDATE""",
            (token_hash,),
        )
        invitation = cursor.fetchone()
        if invitation is None:
            raise HTTPException(status_code=400, detail="Invalid or expired invitation")
        invitation_id, invitation_org_id, invitation_email, invitation_role_id = invitation

        # Re-check at accept time, not just at invite creation: the invitation's
        # ON CONFLICT below would otherwise reset the password of any existing
        # user with this email. Only allow that for a user who already belongs
        # to this organization (the sanctioned access-recovery flow).
        cursor.execute(
            """SELECT EXISTS (
                   SELECT 1 FROM memberships m
                   WHERE m.user_id = u.id AND m.organization_id = %s
               )
               FROM users u WHERE u.email = %s""",
            (invitation_org_id, invitation_email),
        )
        existing_user = cursor.fetchone()
        if existing_user is not None and not existing_user[0]:
            raise HTTPException(
                status_code=409,
                detail="A user with this email already exists outside this organization",
            )

        cursor.execute(
            """INSERT INTO users (id, email, display_name, password_hash)
               VALUES (%s, %s, %s, crypt(%s, gen_salt('bf')))
               ON CONFLICT (email) DO UPDATE SET
                 display_name = EXCLUDED.display_name, password_hash = EXCLUDED.password_hash
               RETURNING id""",
            (str(uuid4()), invitation_email, request.display_name, request.password),
        )
        user_id = cursor.fetchone()[0]
        cursor.execute(
            """INSERT INTO memberships (id, organization_id, user_id, role_id)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (organization_id, user_id, role_id) DO NOTHING""",
            (str(uuid4()), invitation_org_id, user_id, invitation_role_id),
        )
        cursor.execute(
            "UPDATE invitations SET accepted_at = CURRENT_TIMESTAMP WHERE id = %s",
            (invitation_id,),
        )
        identity = {"user_id": user_id, "organization_id": invitation_org_id}
        _insert_audit(
            cursor,
            identity=identity,
            event_type="invitation_accepted",
            subject_type="invitation",
            subject_id=invitation_id,
        )
    return {"access_token": issue_token(**identity, secret=auth_secret()), "token_type": "bearer"}


@app.get("/healthz", tags=["operations"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "environment": "development"}


def require_gateway_authorization(authorization: str | None) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not gateway_token_is_valid(token):
        raise HTTPException(status_code=401, detail="Invalid gateway credentials")


@app.post("/api/v1/gateway/imu-packets", status_code=202, tags=["gateway"])
async def ingest_imu_packet(
    packet: GatewayIMUPacket,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """Persist one raw event, then publish it to local WebSocket listeners.

    202, not 200: the guarantee is that the raw event is durably stored. The
    signal-quality and preprocessing fields in the response are best-effort
    derived context computed inline for the dev scaffold, not part of that
    guarantee -- ``preprocessing.status`` / ``metric_persisted`` report whether
    each downstream step actually ran.
    """
    require_gateway_authorization(authorization)
    payload = packet.model_dump(mode="json")
    canonical_payload = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    payload_sha256 = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    chunk_id = str(uuid4())
    event_id = str(uuid4())
    quality_report: dict[str, Any]
    session_events: list[dict[str, Any]]
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT rs.organization_id, ea.id, rs.episode_id, rs.calibration_id
               FROM rehab_sessions rs
               JOIN exercise_attempts ea ON ea.rehab_session_id = rs.id
               WHERE rs.id = %s AND rs.source_kind = %s AND ea.ended_at IS NULL
               ORDER BY ea.started_at DESC LIMIT 1""",
            (packet.session_id, packet.origin),
        )
        session = cursor.fetchone()
        if session is None:
            raise HTTPException(status_code=422, detail="Unknown or incompatible gateway session")
        organization_id, attempt_id, episode_id, existing_calibration_id = session
        cursor.execute(
            """SELECT id FROM sensor_devices
               WHERE organization_id = %s AND device_identifier = %s""",
            (organization_id, packet.device_id),
        )
        device = cursor.fetchone()
        if device is None:
            raise HTTPException(status_code=422, detail="Unregistered gateway device")
        # Idempotency: the same (session, sensor, sequence) is one physical
        # sample. Reject a replay before it can create a duplicate chunk/event
        # (the unique index from migration 0015 is the race-proof backstop).
        cursor.execute(
            """SELECT 1 FROM gateway_packet_events
               WHERE rehab_session_id = %s AND sensor_role = %s AND sequence_number = %s""",
            (packet.session_id, packet.sensor_role, packet.sequence_number),
        )
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Duplicate gateway packet")
        cursor.execute(
            """INSERT INTO raw_imu_chunks
               (id, organization_id, exercise_attempt_id, sensor_device_id, storage_uri, sha256,
                packet_count, validation_status, captured_at)
               VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s)""",
            (
                chunk_id,
                organization_id,
                attempt_id,
                device[0],
                f"postgres://gateway_packet_events/{chunk_id}",
                payload_sha256,
                packet.validation_status,
                packet.timestamp_gateway,
            ),
        )
        cursor.execute(
            """INSERT INTO gateway_packet_events
               (id, organization_id, rehab_session_id, raw_imu_chunk_id, device_id, sensor_role,
                sequence_number, timestamp_device, timestamp_gateway, payload)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                event_id,
                organization_id,
                packet.session_id,
                chunk_id,
                packet.device_id,
                packet.sensor_role,
                packet.sequence_number,
                packet.timestamp_device,
                packet.timestamp_gateway,
                Json(payload),
            ),
        )
        # Signal quality is re-derived from the whole session on every packet.
        # For the synthetic-replay dev scaffold a session is tens of events; the
        # LIMIT is a guard against a pathologically long stream turning this into
        # an O(n^2) reprocess. It keeps the earliest events, so the static
        # calibration window (the only part the gate acts on) is unaffected.
        # A durable per-attempt aggregation is a production concern -- see
        # unsolved-problems.md.
        cursor.execute(
            """SELECT payload FROM gateway_packet_events
               WHERE rehab_session_id = %s ORDER BY received_at, id LIMIT 6000""",
            (packet.session_id,),
        )
        session_events = [row[0] for row in cursor.fetchall()]
        quality_report = evaluate_signal_quality(session_events).as_dict()
        calibration_id: str | None = None
        if (
            quality_report["level"] == "HIGH"
            and 3.0 <= quality_report["calibration_duration_seconds"] <= 5.0
            and existing_calibration_id is None
        ):
            calibration_id = str(uuid4())
            cursor.execute(
                """INSERT INTO calibrations
                   (id, organization_id, episode_id, parameters, algorithm_version)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    calibration_id,
                    organization_id,
                    episode_id,
                    Json(
                        {
                            "kind": "technical_static_window",
                            "signal_quality": quality_report,
                            "source_raw_imu_chunk_id": chunk_id,
                            "limitations": [
                                "Not an orientation or anatomical calibration; "
                                "no angle is estimated."
                            ],
                        }
                    ),
                    "algorithm-static-calibration-gate-v1",
                ),
            )
            cursor.execute(
                "UPDATE rehab_sessions SET calibration_id = %s WHERE id = %s",
                (calibration_id, packet.session_id),
            )
        quality_report["calibration_recorded"] = calibration_id is not None
        cursor.execute(
            """INSERT INTO signal_quality
               (id, organization_id, exercise_attempt_id, raw_imu_chunk_id,
                algorithm_version_id, result)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                str(uuid4()),
                organization_id,
                attempt_id,
                chunk_id,
                "algorithm-signal-quality-v1",
                Json(quality_report),
            ),
        )
    preprocessing: dict[str, Any] = {"status": "skipped_quality_gate"}
    preprocessing_metric_id: str | None = None
    shadow_prediction: dict[str, Any] | None = None
    shadow_prediction_id: str | None = None
    gate_open = bool(quality_report["scoring_permitted"])
    forced = ml_force_inference_enabled() and not gate_open
    # The persisted signal_quality row and the response keep the real verdict;
    # only the ML branch sees this forced copy (see ml_force_inference_enabled).
    ml_quality = (
        {**quality_report, "scoring_permitted": True, "gate_overridden": True}
        if forced
        else quality_report
    )
    if gate_open or forced:
        # Preprocessing now runs in-process (Stage 9: monolith, no separate
        # biomechanics service). It is a pure resample of the session's events.
        technical_result = preprocess_transport_events(
            session_events, signal_quality=ml_quality
        )
        technical_frames = list(technical_result.frames)
        preprocessing = {
            "status": "completed" if technical_result.allowed else "blocked",
            "reasons": list(technical_result.reasons),
            "parameters": technical_result.parameters,
            "frame_count": len(technical_frames),
        }
        # The raw event and its signal_quality row are already committed -- that
        # is the contract this endpoint promises. This derived metric is
        # additive lineage in its own transaction: if it fails, surface that in
        # the response rather than 500-ing (which would invite a retry that the
        # 0015 dedup index now rejects anyway).
        metric_id = str(uuid4())
        try:
            with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO derived_metrics
                       (id, organization_id, exercise_attempt_id, raw_imu_chunk_id,
                        calibration_id, algorithm_version_id, name, value)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        metric_id,
                        organization_id,
                        attempt_id,
                        chunk_id,
                        calibration_id or existing_calibration_id,
                        "algorithm-imu-preprocessing-v1",
                        "technical_preprocessing",
                        Json(
                            {
                                "status": preprocessing["status"],
                                "reasons": preprocessing["reasons"],
                                "frame_count": preprocessing["frame_count"],
                                "parameters": preprocessing["parameters"],
                                "limitations": [
                                    "No sensor fusion, angle estimation, rep segmentation, "
                                    "scoring, "
                                    "or clinical feedback."
                                ],
                            }
                        ),
                    ),
                )
        except psycopg.Error:
            preprocessing["metric_persisted"] = False
        else:
            preprocessing_metric_id = metric_id
            preprocessing["metric_persisted"] = True

        # Stage 9: shadow-mode ML interpretation. Abstains unless a validated
        # checkpoint is present in app/ml/checkpoints/. Own transaction, never
        # patient-visible, never affects score or feedback.
        shadow_prediction = run_shadow_inference(technical_frames, ml_quality)
        if forced:
            shadow_prediction["gate_overridden"] = True
            shadow_prediction["signal_quality_level"] = quality_report["level"]
            shadow_prediction["signal_quality_reasons"] = list(quality_report["reasons"])
        shadow_id = str(uuid4())
        try:
            with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO shadow_predictions
                       (id, organization_id, exercise_attempt_id, raw_imu_chunk_id,
                        algorithm_version_id, prediction)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        shadow_id,
                        organization_id,
                        attempt_id,
                        chunk_id,
                        "algorithm-shadow-inference-v1",
                        Json(shadow_prediction),
                    ),
                )
        except psycopg.Error:
            shadow_prediction["persisted"] = False
        else:
            shadow_prediction_id = shadow_id
            shadow_prediction["persisted"] = True
    event = {
        "event_id": event_id,
        **payload,
        "signal_quality": quality_report,
        "preprocessing": preprocessing,
        "preprocessing_metric_id": preprocessing_metric_id,
        "shadow_prediction": shadow_prediction,
        "shadow_prediction_id": shadow_prediction_id,
    }
    await gateway_streams.publish(packet.session_id, event)
    return {
        "event_id": event_id,
        "raw_imu_chunk_id": chunk_id,
        "signal_quality": quality_report,
        "preprocessing": preprocessing,
        "preprocessing_metric_id": preprocessing_metric_id,
        "shadow_prediction": shadow_prediction,
        "shadow_prediction_id": shadow_prediction_id,
    }


def _websocket_gateway_token(websocket: WebSocket) -> str:
    """Prefer a header; fall back to the query string for browser WS clients.

    Browsers cannot set headers on a WebSocket handshake, so ``?token=`` stays
    supported, but a non-browser caller (the gateway itself) should send the
    token in ``Authorization: Bearer`` or the ``Sec-WebSocket-Protocol`` header
    to keep it out of access logs and URLs.
    """
    header = websocket.headers.get("authorization", "")
    scheme, _, bearer = header.partition(" ")
    if scheme.lower() == "bearer" and bearer:
        return bearer
    protocol = websocket.headers.get("sec-websocket-protocol", "")
    if protocol:
        return protocol.split(",")[0].strip()
    return websocket.query_params.get("token", "")


@app.websocket("/api/v1/gateway/sessions/{session_id}/stream")
async def stream_gateway_packets(websocket: WebSocket, session_id: str) -> None:
    """Authenticated live transport stream, intentionally separate from scoring."""
    if not gateway_token_is_valid(_websocket_gateway_token(websocket)):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    requested_protocol = websocket.headers.get("sec-websocket-protocol", "")
    negotiated_protocol = requested_protocol.split(",")[0].strip() if requested_protocol else None
    await gateway_streams.connect(session_id, websocket, subprotocol=negotiated_protocol)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        gateway_streams.disconnect(session_id, websocket)


class ExerciseAttemptRequest(BaseModel):
    source_kind: str = Field(pattern="^(synthetic|hardware)$")
    exercise_prescription_id: str


@app.post("/api/v1/episodes/{episode_id}/exercise-attempts", status_code=201, tags=["gateway"])
def start_exercise_attempt(
    episode_id: str, request: ExerciseAttemptRequest, identity: Identity
) -> dict[str, str]:
    """Open the (rehab_session, exercise_attempt) pair gateway ingestion requires.

    ``POST /api/v1/gateway/imu-packets`` only accepts packets for an
    already-open pair matched by ``session_id`` -- this is where that pair is
    created, so a real (or synthetic) sensor stream has something to ingest
    against.
    """
    organization_id = str(identity["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT patient.user_id FROM episodes_of_care episode
               JOIN patients patient ON patient.id = episode.patient_id
               WHERE episode.id = %s AND episode.organization_id = %s""",
            (episode_id, organization_id),
        )
        episode = cursor.fetchone()
        if episode is None or not can_view_patient(
            roles=frozenset(identity["roles"]),
            patient_user_id=episode[0],
            user_id=str(identity["user_id"]),
        ):
            raise HTTPException(status_code=404, detail="Episode not found")
        cursor.execute(
            """SELECT 1 FROM exercise_prescriptions ep
               JOIN protocol_assignments pa ON pa.id = ep.protocol_assignment_id
               WHERE ep.id = %s AND ep.organization_id = %s AND pa.episode_id = %s""",
            (request.exercise_prescription_id, organization_id, episode_id),
        )
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=422, detail="Unknown exercise prescription for this episode"
            )
        session_id = str(uuid4())
        attempt_id = str(uuid4())
        cursor.execute(
            """INSERT INTO rehab_sessions
               (id, organization_id, episode_id, source_kind, started_at)
               VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)""",
            (session_id, organization_id, episode_id, request.source_kind),
        )
        cursor.execute(
            """INSERT INTO exercise_attempts
               (id, organization_id, rehab_session_id, exercise_prescription_id, started_at)
               VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)""",
            (attempt_id, organization_id, session_id, request.exercise_prescription_id),
        )
        _insert_audit(
            cursor,
            identity=identity,
            event_type="exercise_attempt_started",
            subject_type="exercise_attempt",
            subject_id=attempt_id,
        )
    return {"session_id": session_id, "exercise_attempt_id": attempt_id}


@app.post("/api/v1/exercise-attempts/{attempt_id}/complete", tags=["gateway"])
def complete_exercise_attempt(attempt_id: str, identity: Identity) -> dict[str, object]:
    organization_id = str(identity["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT patient.user_id FROM exercise_attempts attempt
               JOIN rehab_sessions session ON session.id = attempt.rehab_session_id
               JOIN episodes_of_care episode ON episode.id = session.episode_id
               JOIN patients patient ON patient.id = episode.patient_id
               WHERE attempt.id = %s AND attempt.organization_id = %s""",
            (attempt_id, organization_id),
        )
        row = cursor.fetchone()
        if row is None or not can_view_patient(
            roles=frozenset(identity["roles"]),
            patient_user_id=row[0],
            user_id=str(identity["user_id"]),
        ):
            raise HTTPException(status_code=404, detail="Exercise attempt not found")
        cursor.execute(
            """UPDATE exercise_attempts SET ended_at = CURRENT_TIMESTAMP
               WHERE id = %s AND ended_at IS NULL""",
            (attempt_id,),
        )
        _insert_audit(
            cursor,
            identity=identity,
            event_type="exercise_attempt_completed",
            subject_type="exercise_attempt",
            subject_id=attempt_id,
        )
    return {"exercise_attempt_id": attempt_id, "status": "completed"}


class SensorDeviceRequest(BaseModel):
    device_identifier: str = Field(min_length=1, max_length=200)
    model: str | None = Field(default=None, max_length=200)


@app.post("/api/v1/sensor-devices", tags=["gateway"])
def register_sensor_device(request: SensorDeviceRequest, identity: Identity) -> dict[str, str]:
    """Idempotent upsert so a patient's own browser can register its own sensors."""
    organization_id = str(identity["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO sensor_devices (id, organization_id, device_identifier, model)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (organization_id, device_identifier)
               DO UPDATE SET model = EXCLUDED.model
               RETURNING id""",
            (str(uuid4()), organization_id, request.device_identifier, request.model),
        )
        device_id = cursor.fetchone()[0]
        _insert_audit(
            cursor,
            identity=identity,
            event_type="sensor_device_registered",
            subject_type="sensor_device",
            subject_id=device_id,
        )
    return {"id": device_id}


@app.get("/api/v1/rehab-sessions/{session_id}/signal-quality", tags=["signal-quality"])
def get_signal_quality(session_id: str, identity: Identity) -> dict[str, object]:
    """Return technical status only, with normal tenant and patient access checks."""
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT sq.result, sq.created_at, patient.user_id
               FROM rehab_sessions session
               JOIN episodes_of_care episode ON episode.id = session.episode_id
               JOIN patients patient ON patient.id = episode.patient_id
               LEFT JOIN LATERAL (
                   SELECT result, created_at FROM signal_quality
                   WHERE exercise_attempt_id IN (
                       SELECT id FROM exercise_attempts WHERE rehab_session_id = session.id
                   )
                   ORDER BY created_at DESC LIMIT 1
               ) sq ON TRUE
               WHERE session.id = %s AND session.organization_id = %s""",
            (session_id, str(identity["organization_id"])),
        )
        row = cursor.fetchone()
        if row is None or not can_view_patient(
            roles=frozenset(identity["roles"]),
            patient_user_id=row[2],
            user_id=str(identity["user_id"]),
        ):
            raise HTTPException(status_code=404, detail="Rehabilitation session not found")
        _insert_audit(
            cursor,
            identity=identity,
            event_type="signal_quality_view",
            subject_type="rehab_session",
            subject_id=session_id,
        )
    if row[0] is None:
        return {
            "session_id": session_id,
            "level": "INVALID",
            "reasons": ["signal_quality_not_available"],
            "scoring_permitted": False,
            "clinical_scoring": False,
        }
    result = dict(row[0])
    return {
        "session_id": session_id,
        "assessed_at": row[1],
        "clinical_scoring": False,
        **result,
    }


@app.get("/api/v1/demo", tags=["development"])
def get_demo() -> dict[str, object]:
    """Expose only the seed-shaped synthetic fixture to the local demo pages."""
    return demo_snapshot()


@app.get("/api/v1/auth/me", tags=["identity"])
def get_current_user(identity: Identity) -> dict[str, object]:
    return {
        "user_id": identity["user_id"],
        "organization_id": identity["organization_id"],
        "roles": sorted(identity["roles"]),
    }


PATIENT_LIST_ROLES = frozenset({"clinician", "rehabilitologist", "organization_admin"})


def _active_episode_id(cursor: Any, *, patient_id: str, organization_id: str) -> str | None:
    """Most recent episode for the patient.

    ``episodes_of_care.status`` is free text, not a constrained enum (see
    migration 0002), and the seeded demo episode uses the marker
    ``development_fixture`` rather than ``active`` -- so this deliberately
    does not filter on a specific status value, only recency.
    """
    cursor.execute(
        """SELECT id FROM episodes_of_care
           WHERE patient_id = %s AND organization_id = %s
           ORDER BY created_at DESC LIMIT 1""",
        (patient_id, organization_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None


@app.get("/api/v1/patients/me", tags=["patients"])
def get_current_patient(identity: Identity) -> dict[str, object]:
    """Self-lookup for a logged-in patient -- the only way to learn one's own patient_id."""
    organization_id = str(identity["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, display_name, post_op_day FROM patients
               WHERE user_id = %s AND organization_id = %s""",
            (str(identity["user_id"]), organization_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No patient record for this user")
        active_episode_id = _active_episode_id(
            cursor, patient_id=row[0], organization_id=organization_id
        )
        _insert_audit(
            cursor,
            identity=identity,
            event_type="patient_self_view",
            subject_type="patient",
            subject_id=row[0],
        )
    return {
        "id": row[0],
        "display_name": row[1],
        "post_op_day": row[2],
        "active_episode_id": active_episode_id,
    }


@app.get("/api/v1/patients", tags=["patients"])
def list_patients(identity: Identity) -> list[dict[str, object]]:
    """Org-scoped patient list for a clinician's dashboard queue."""
    require_roles(identity, PATIENT_LIST_ROLES)
    organization_id = str(identity["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, display_name, post_op_day FROM patients
               WHERE organization_id = %s ORDER BY display_name""",
            (organization_id,),
        )
        rows = cursor.fetchall()
        results = [
            {
                "id": row[0],
                "display_name": row[1],
                "post_op_day": row[2],
                "active_episode_id": _active_episode_id(
                    cursor, patient_id=row[0], organization_id=organization_id
                ),
            }
            for row in rows
        ]
        _insert_audit(
            cursor,
            identity=identity,
            event_type="patients_list_view",
            subject_type="organization",
            subject_id=organization_id,
        )
    return results


@app.get("/api/v1/patients/{patient_id}", tags=["patients"])
def get_patient(patient_id: str, identity: Identity) -> dict[str, object]:
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, display_name, post_op_day, user_id FROM patients
               WHERE id = %s AND organization_id = %s""",
            (patient_id, str(identity["organization_id"])),
        )
        row = cursor.fetchone()
        if row is None or not can_view_patient(
            roles=frozenset(identity["roles"]),
            patient_user_id=row[3],
            user_id=str(identity["user_id"]),
        ):
            raise HTTPException(status_code=404, detail="Patient not found")
        _insert_audit(
            cursor,
            identity=identity,
            event_type="patient_view",
            subject_type="patient",
            subject_id=patient_id,
        )
    return {"id": row[0], "display_name": row[1], "post_op_day": row[2]}


PROTOCOL_AUTHOR_ROLES = frozenset({"clinician", "rehabilitologist"})


class PrescriptionConfiguration(BaseModel):
    sets: int | None = Field(default=None, ge=1)
    repetitions: int | None = Field(default=None, ge=1)
    frequency: str | None = Field(default=None, max_length=100)
    target_rom_degrees: float | None = Field(default=None, ge=0, le=180)
    tempo: str | None = Field(default=None, max_length=100)
    hold_seconds: float | None = Field(default=None, ge=0)
    restriction_sources: list[dict[str, Any]] = Field(default_factory=list)


class ProtocolVersionRequest(BaseModel):
    protocol_template_id: str
    exercise_definition_id: str
    prescription: PrescriptionConfiguration


@app.get("/api/v1/exercise-definitions", tags=["protocols"])
def list_exercise_definitions(identity: Identity) -> list[dict[str, object]]:
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, name, definition_version, configuration
               FROM exercise_definitions
               WHERE organization_id = %s ORDER BY name, definition_version DESC""",
            (str(identity["organization_id"]),),
        )
        definitions = cursor.fetchall()
    return [
        {"id": row[0], "name": row[1], "version": row[2], "configuration": row[3]}
        for row in definitions
    ]


@app.get("/api/v1/episodes/{episode_id}/protocol", tags=["protocols"])
def get_current_protocol(episode_id: str, identity: Identity) -> dict[str, object]:
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT pa.id, pa.version, pt.id, pt.name, pt.approval_state,
                      ed.id, ed.name, ed.definition_version, ep.id,
                      ep.configuration, patient.user_id
               FROM protocol_assignments pa
               JOIN protocol_templates pt ON pt.id = pa.protocol_template_id
               JOIN episodes_of_care episode ON episode.id = pa.episode_id
               JOIN patients patient ON patient.id = episode.patient_id
               JOIN exercise_prescriptions ep ON ep.protocol_assignment_id = pa.id
               JOIN exercise_definitions ed ON ed.id = ep.exercise_definition_id
               WHERE pa.episode_id = %s AND pa.organization_id = %s
                 AND pa.superseded_at IS NULL
               ORDER BY pa.version DESC, ep.created_at""",
            (episode_id, str(identity["organization_id"])),
        )
        rows = cursor.fetchall()
        if not rows or not can_view_patient(
            roles=frozenset(identity["roles"]),
            patient_user_id=rows[0][10],
            user_id=str(identity["user_id"]),
        ):
            raise HTTPException(status_code=404, detail="Protocol not found")
        _insert_audit(
            cursor,
            identity=identity,
            event_type="protocol_view",
            subject_type="protocol_assignment",
            subject_id=rows[0][0],
        )
    return {
        "assignment_id": rows[0][0],
        "version": rows[0][1],
        "template": {"id": rows[0][2], "name": rows[0][3], "approval_state": rows[0][4]},
        "exercises": [
            {
                "id": row[5],
                "name": row[6],
                "version": row[7],
                "prescription_id": row[8],
                "prescription": row[9],
            }
            for row in rows
        ],
    }


@app.get("/api/v1/episodes/{episode_id}/protocol-history", tags=["protocols"])
def get_protocol_history(episode_id: str, identity: Identity) -> list[dict[str, object]]:
    """Return immutable assignment versions, newest first, for the tenant."""
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT pa.id, pa.version, pa.created_at, pa.superseded_at,
                      ed.id, ed.name, ed.definition_version, ep.id, ep.configuration,
                      patient.user_id
               FROM protocol_assignments pa
               JOIN episodes_of_care episode ON episode.id = pa.episode_id
               JOIN patients patient ON patient.id = episode.patient_id
               JOIN exercise_prescriptions ep ON ep.protocol_assignment_id = pa.id
               JOIN exercise_definitions ed ON ed.id = ep.exercise_definition_id
               WHERE pa.episode_id = %s AND pa.organization_id = %s
               ORDER BY pa.version DESC, ep.created_at""",
            (episode_id, str(identity["organization_id"])),
        )
        rows = cursor.fetchall()
        if not rows or not can_view_patient(
            roles=frozenset(identity["roles"]),
            patient_user_id=rows[0][9],
            user_id=str(identity["user_id"]),
        ):
            raise HTTPException(status_code=404, detail="Protocol history not found")
        _insert_audit(
            cursor,
            identity=identity,
            event_type="protocol_history_view",
            subject_type="episode",
            subject_id=episode_id,
        )
    return [
        {
            "assignment_id": row[0],
            "version": row[1],
            "created_at": row[2],
            "superseded_at": row[3],
            "exercise": {"id": row[4], "name": row[5], "version": row[6]},
            "prescription_id": row[7],
            "prescription": row[8],
        }
        for row in rows
    ]


@app.post("/api/v1/episodes/{episode_id}/protocol-versions", status_code=201, tags=["protocols"])
def create_protocol_version(
    episode_id: str, request: ProtocolVersionRequest, identity: Identity
) -> dict[str, object]:
    require_roles(identity, PROTOCOL_AUTHOR_ROLES)
    organization_id = str(identity["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM episodes_of_care WHERE id = %s AND organization_id = %s FOR UPDATE",
            (episode_id, organization_id),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        cursor.execute(
            "SELECT id FROM clinicians WHERE user_id = %s AND organization_id = %s",
            (str(identity["user_id"]), organization_id),
        )
        clinician = cursor.fetchone()
        if clinician is None:
            raise HTTPException(status_code=403, detail="No clinician record for this user")
        cursor.execute(
            """SELECT 1 FROM protocol_templates
               WHERE id = %s AND organization_id = %s AND approval_state != 'retired'""",
            (request.protocol_template_id, organization_id),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Unavailable protocol template")
        cursor.execute(
            "SELECT 1 FROM exercise_definitions WHERE id = %s AND organization_id = %s",
            (request.exercise_definition_id, organization_id),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Unavailable exercise definition")
        # Lock existing versions before calculating the next one.  The tenant
        # predicate is intentional: a version in another organization must
        # never influence this assignment history.
        cursor.execute(
            """SELECT version FROM protocol_assignments
               WHERE episode_id = %s AND organization_id = %s
               ORDER BY version DESC FOR UPDATE""",
            (episode_id, organization_id),
        )
        existing_versions = [row[0] for row in cursor.fetchall()]
        version = (existing_versions[0] if existing_versions else 0) + 1
        assignment_id = str(uuid4())
        prescription_id = str(uuid4())
        cursor.execute(
            """INSERT INTO protocol_assignments
               (id, organization_id, episode_id, protocol_template_id, version,
                assigned_by_clinician_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                assignment_id,
                organization_id,
                episode_id,
                request.protocol_template_id,
                version,
                clinician[0],
            ),
        )
        prescription = request.prescription.model_dump()
        prescription["approval_state"] = "draft"
        cursor.execute(
            """INSERT INTO exercise_prescriptions
               (id, organization_id, protocol_assignment_id, exercise_definition_id, configuration)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                prescription_id,
                organization_id,
                assignment_id,
                request.exercise_definition_id,
                Json(prescription),
            ),
        )
        cursor.execute(
            """UPDATE protocol_assignments SET superseded_at = CURRENT_TIMESTAMP
               WHERE episode_id = %s AND organization_id = %s AND id != %s
                 AND superseded_at IS NULL""",
            (episode_id, organization_id, assignment_id),
        )
        _insert_audit(
            cursor,
            identity=identity,
            event_type="protocol_version_created",
            subject_type="protocol_assignment",
            subject_id=assignment_id,
        )
    return {"assignment_id": assignment_id, "prescription_id": prescription_id, "version": version}


ALERT_ACTION_ROLES = frozenset({"clinician", "rehabilitologist", "organization_admin"})


class SymptomCheckRequest(BaseModel):
    """Post-session patient-reported check; never itself a diagnosis (NTZ 14.1)."""

    pain_before: float | None = Field(default=None, ge=0, le=10)
    pain_after: float | None = Field(default=None, ge=0, le=10)
    difficulty: float | None = Field(default=None, ge=0, le=10)
    knee_feels: str | None = Field(
        default=None, pattern="^(better|same|slightly_worse|much_worse)$"
    )
    reported_symptoms: list[str] = Field(default_factory=list, max_length=128)

    @field_validator("reported_symptoms")
    @classmethod
    def _normalise_symptoms(cls, value: list[str]) -> list[str]:
        """Trim, lowercase, format-check and de-duplicate; cap the count.

        An unknown but well-formed key is still allowed through -- the safety
        engine deliberately routes unconfigured symptoms to YELLOW review. This
        only stops unbounded lists and free-text abuse from reaching the alert
        trigger and the audit log.
        """
        seen: list[str] = []
        for raw in value:
            key = raw.strip().lower()
            if not key:
                continue
            if not _SYMPTOM_KEY.fullmatch(key):
                raise ValueError(f"invalid symptom key: {raw!r}")
            if key not in seen:
                seen.append(key)
        if len(seen) > MAX_REPORTED_SYMPTOMS:
            raise ValueError(f"too many reported symptoms (max {MAX_REPORTED_SYMPTOMS})")
        return seen


class AlertActionRequest(BaseModel):
    action_type: str = Field(pattern="^(acknowledged|dismissed)$")
    note: str | None = Field(default=None, max_length=2000)


@app.post(
    "/api/v1/rehab-sessions/{session_id}/symptom-check", status_code=201, tags=["safety"]
)
def submit_symptom_check(
    session_id: str, request: SymptomCheckRequest, identity: Identity
) -> dict[str, object]:
    """Evaluate a symptom check against the org's deterministic safety policy.

    Only a clinically_approved policy can ever produce a real GREEN/YELLOW/RED
    level; an unapproved or missing policy withholds a result rather than
    guessing, and no alert row is created for it.
    """
    organization_id = str(identity["organization_id"])
    symptom_check_id = str(uuid4())
    assessment_id = str(uuid4())
    answers = request.model_dump()
    alert_id: str | None = None

    # One transaction for the whole workflow: the symptom check, its safety
    # assessment (persisted for every outcome, not only YELLOW/RED), any alert,
    # and the audit rows either all commit together or none do.
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT rs.episode_id, patient.user_id
               FROM rehab_sessions rs
               JOIN episodes_of_care episode ON episode.id = rs.episode_id
               JOIN patients patient ON patient.id = episode.patient_id
               WHERE rs.id = %s AND rs.organization_id = %s""",
            (session_id, organization_id),
        )
        session = cursor.fetchone()
        if session is None or not can_view_patient(
            roles=frozenset(identity["roles"]),
            patient_user_id=session[1],
            user_id=str(identity["user_id"]),
        ):
            raise HTTPException(status_code=404, detail="Rehabilitation session not found")
        episode_id = session[0]

        cursor.execute(
            """INSERT INTO symptom_checks (id, organization_id, rehab_session_id, answers)
               VALUES (%s, %s, %s, %s)""",
            (symptom_check_id, organization_id, session_id, Json(answers)),
        )

        cursor.execute(
            """SELECT version, configuration FROM safety_rule_policies
               WHERE organization_id = %s ORDER BY created_at DESC LIMIT 1""",
            (organization_id,),
        )
        policy_row = cursor.fetchone()

        if policy_row is None:
            assessment = {
                "status": "withheld",
                "level": None,
                "reasons": ["no_policy_configured"],
                "policy_version": None,
            }
        else:
            policy_version, configuration = policy_row
            try:
                policy = SafetyRulePolicy.from_configuration(
                    {**configuration, "version": policy_version}
                )
            except ValueError as error:
                # A malformed stored policy must withhold a result, not 500 the
                # patient and leave the check evaluated against nothing.
                assessment = {
                    "status": "withheld",
                    "level": None,
                    "reasons": [f"policy_invalid:{error}"],
                    "policy_version": policy_version,
                }
            else:
                result = evaluate_safety_rules(
                    policy=policy,
                    reported_symptoms=frozenset(request.reported_symptoms),
                    pain_before=request.pain_before,
                    pain_after=request.pain_after,
                )
                assessment = {
                    "status": result.status.value,
                    "level": result.level.value if result.level is not None else None,
                    "reasons": list(result.reasons),
                    "policy_version": result.policy_version,
                }

        if assessment["level"] in ("YELLOW", "RED"):
            alert_id = str(uuid4())
            cursor.execute(
                """INSERT INTO alerts
                   (id, organization_id, episode_id, severity, rule_version, trigger)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    alert_id,
                    organization_id,
                    episode_id,
                    assessment["level"].lower(),
                    assessment["policy_version"],
                    Json({"symptom_check_id": symptom_check_id, "reasons": assessment["reasons"]}),
                ),
            )
            _insert_audit(
                cursor,
                identity=identity,
                event_type="alert_created",
                subject_type="alert",
                subject_id=alert_id,
            )

        cursor.execute(
            """INSERT INTO safety_assessments
               (id, organization_id, rehab_session_id, symptom_check_id, status, level,
                reasons, policy_version, alert_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                assessment_id,
                organization_id,
                session_id,
                symptom_check_id,
                assessment["status"],
                assessment["level"],
                Json(assessment["reasons"]),
                assessment["policy_version"],
                alert_id,
            ),
        )
        _insert_audit(
            cursor,
            identity=identity,
            event_type="symptom_check_submitted",
            subject_type="symptom_check",
            subject_id=symptom_check_id,
        )

    return {
        "symptom_check_id": symptom_check_id,
        "assessment_id": assessment_id,
        "safety_assessment": assessment,
        "alert_id": alert_id,
    }


@app.get("/api/v1/episodes/{episode_id}/alerts", tags=["safety"])
def list_alerts(episode_id: str, identity: Identity) -> list[dict[str, object]]:
    organization_id = str(identity["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT patient.user_id FROM episodes_of_care episode
               JOIN patients patient ON patient.id = episode.patient_id
               WHERE episode.id = %s AND episode.organization_id = %s""",
            (episode_id, organization_id),
        )
        episode = cursor.fetchone()
        if episode is None or not can_view_patient(
            roles=frozenset(identity["roles"]),
            patient_user_id=episode[0],
            user_id=str(identity["user_id"]),
        ):
            raise HTTPException(status_code=404, detail="Episode not found")
        cursor.execute(
            """SELECT a.id, a.severity, a.rule_version, a.trigger, a.created_at,
                      (SELECT ca.action_type FROM clinician_actions ca
                       WHERE ca.alert_id = a.id ORDER BY ca.created_at DESC LIMIT 1)
               FROM alerts a
               WHERE a.episode_id = %s AND a.organization_id = %s
               ORDER BY a.created_at DESC""",
            (episode_id, organization_id),
        )
        rows = cursor.fetchall()
        _insert_audit(
            cursor,
            identity=identity,
            event_type="alerts_view",
            subject_type="episode",
            subject_id=episode_id,
        )
    return [
        {
            "id": row[0],
            "severity": row[1],
            "rule_version": row[2],
            "trigger": row[3],
            "created_at": row[4],
            "status": row[5] or "open",
        }
        for row in rows
    ]


@app.post("/api/v1/alerts/{alert_id}/actions", status_code=201, tags=["safety"])
def create_alert_action(
    alert_id: str, request: AlertActionRequest, identity: Identity
) -> dict[str, object]:
    """Record acknowledge/dismiss as an append-only clinician action.

    Never edits or deletes the alert itself; the alert's displayed status is
    always derived from the latest recorded action.
    """
    require_roles(identity, ALERT_ACTION_ROLES)
    organization_id = str(identity["organization_id"])
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM alerts WHERE id = %s AND organization_id = %s",
            (alert_id, organization_id),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        cursor.execute(
            "SELECT id FROM clinicians WHERE user_id = %s AND organization_id = %s",
            (str(identity["user_id"]), organization_id),
        )
        clinician = cursor.fetchone()
        action_id = str(uuid4())
        cursor.execute(
            """INSERT INTO clinician_actions
               (id, organization_id, alert_id, clinician_id, action_type, details)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                action_id,
                organization_id,
                alert_id,
                clinician[0] if clinician is not None else None,
                request.action_type,
                Json({"note": request.note}),
            ),
        )
        _insert_audit(
            cursor,
            identity=identity,
            event_type=f"alert_{request.action_type}",
            subject_type="alert",
            subject_id=alert_id,
        )
    return {"action_id": action_id, "alert_id": alert_id, "status": request.action_type}
