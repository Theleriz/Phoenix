"""HTTP entry point for the local PHOENIX development environment."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.types.json import Json
from pydantic import BaseModel, Field

from .biomechanics import BiomechanicsClient, PreprocessingUnavailable
from .demo import demo_snapshot
from .security import can_view_patient, issue_token, verify_token
from .signal_quality import evaluate_signal_quality

app = FastAPI(title="PHOENIX API", version="0.1.0", docs_url="/docs")
bearer = HTTPBearer()
INVITATION_ADMIN_ROLES = frozenset({"organization_admin", "technical_admin"})


class GatewayStreams:
    """In-process development fan-out; production needs a durable broker."""

    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = {}

    async def connect(self, session_id: str, client: WebSocket) -> None:
        await client.accept()
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


def biomechanics_client() -> BiomechanicsClient | None:
    url = os.environ.get("PHOENIX_BIOMECHANICS_URL")
    return BiomechanicsClient(url) if url else None


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


def write_audit(
    *, identity: dict[str, object], event_type: str, subject_type: str, subject_id: str
) -> None:
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
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
    write_audit(identity=identity, event_type="login", subject_type="user", subject_id=row[0])
    return {"access_token": issue_token(**identity, secret=auth_secret()), "token_type": "bearer"}


@app.post("/api/v1/invitations", status_code=201, tags=["identity"])
def create_invitation(request: InvitationRequest, identity: Identity) -> dict[str, str]:
    require_roles(identity, INVITATION_ADMIN_ROLES)
    invitation_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM roles WHERE name = %s",
            (request.role,),
        )
        role = cursor.fetchone()
        if role is None:
            raise HTTPException(status_code=422, detail="Unknown role")
        cursor.execute(
            """INSERT INTO invitations
               (id, organization_id, email, role_id, token_hash, expires_at, created_by_user_id)
               VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP + (%s * INTERVAL '1 hour'), %s)""",
            (
                invitation_id,
                str(identity["organization_id"]),
                request.email.lower(),
                role[0],
                token_hash,
                request.expires_in_hours,
                str(identity["user_id"]),
            ),
        )
    write_audit(
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
        cursor.execute(
            """INSERT INTO users (id, email, display_name, password_hash)
               VALUES (%s, %s, %s, crypt(%s, gen_salt('bf')))
               ON CONFLICT (email) DO UPDATE SET
                 display_name = EXCLUDED.display_name, password_hash = EXCLUDED.password_hash
               RETURNING id""",
            (str(uuid4()), invitation[2], request.display_name, request.password),
        )
        user_id = cursor.fetchone()[0]
        cursor.execute(
            """INSERT INTO memberships (id, organization_id, user_id, role_id)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (organization_id, user_id, role_id) DO NOTHING""",
            (str(uuid4()), invitation[1], user_id, invitation[3]),
        )
        cursor.execute(
            "UPDATE invitations SET accepted_at = CURRENT_TIMESTAMP WHERE id = %s",
            (invitation[0],),
        )
    identity = {"user_id": user_id, "organization_id": invitation[1]}
    write_audit(
        identity=identity,
        event_type="invitation_accepted",
        subject_type="invitation",
        subject_id=invitation[0],
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
) -> dict[str, str]:
    """Persist one raw event before publishing it to local WebSocket listeners."""
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
        cursor.execute(
            """SELECT payload FROM gateway_packet_events
               WHERE rehab_session_id = %s ORDER BY received_at, id""",
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
    client = biomechanics_client()
    if quality_report["scoring_permitted"] and client is not None:
        try:
            technical_result = await client.preprocess(
                events=session_events, signal_quality=quality_report
            )
        except PreprocessingUnavailable:
            preprocessing = {"status": "unavailable"}
        else:
            preprocessing = {
                "status": "completed" if technical_result.get("allowed") else "blocked",
                "reasons": technical_result.get("reasons", []),
                "parameters": technical_result.get("parameters", {}),
                "frame_count": len(technical_result.get("frames", [])),
            }
            preprocessing_metric_id = str(uuid4())
            with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO derived_metrics
                       (id, organization_id, exercise_attempt_id, raw_imu_chunk_id, calibration_id,
                        algorithm_version_id, name, value)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        preprocessing_metric_id,
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
    elif quality_report["scoring_permitted"]:
        preprocessing = {"status": "not_configured"}
    event = {
        "event_id": event_id,
        **payload,
        "signal_quality": quality_report,
        "preprocessing": preprocessing,
        "preprocessing_metric_id": preprocessing_metric_id,
    }
    await gateway_streams.publish(packet.session_id, event)
    return {
        "event_id": event_id,
        "raw_imu_chunk_id": chunk_id,
        "signal_quality": quality_report,
        "preprocessing": preprocessing,
        "preprocessing_metric_id": preprocessing_metric_id,
    }


@app.websocket("/api/v1/gateway/sessions/{session_id}/stream")
async def stream_gateway_packets(websocket: WebSocket, session_id: str) -> None:
    """Authenticated live transport stream, intentionally separate from scoring."""
    if not gateway_token_is_valid(websocket.query_params.get("token", "")):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await gateway_streams.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        gateway_streams.disconnect(session_id, websocket)


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
        roles=frozenset(identity["roles"]), patient_user_id=row[3], user_id=str(identity["user_id"])
    ):
        raise HTTPException(status_code=404, detail="Patient not found")
    write_audit(
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
    write_audit(
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
    write_audit(
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
    write_audit(
        identity=identity,
        event_type="protocol_version_created",
        subject_type="protocol_assignment",
        subject_id=assignment_id,
    )
    return {"assignment_id": assignment_id, "prescription_id": prescription_id, "version": version}
