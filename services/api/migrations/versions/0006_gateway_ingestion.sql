-- Stage 6: auditable transport ingestion for the development-only IMU gateway.
-- Packet payloads are kept losslessly; this migration does not add scoring.

CREATE TABLE gateway_packet_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    rehab_session_id TEXT NOT NULL REFERENCES rehab_sessions(id),
    raw_imu_chunk_id TEXT NOT NULL REFERENCES raw_imu_chunks(id),
    device_id TEXT NOT NULL,
    sensor_role TEXT NOT NULL CHECK (sensor_role IN ('thigh', 'shank', 'foot')),
    sequence_number BIGINT NOT NULL CHECK (sequence_number >= 0),
    timestamp_device DOUBLE PRECISION,
    timestamp_gateway TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_gateway_packet_events_session_received
    ON gateway_packet_events (rehab_session_id, received_at);

CREATE TRIGGER gateway_packet_events_immutable
    BEFORE UPDATE OR DELETE ON gateway_packet_events
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();

-- Development-only wiring for the deterministic synthetic replay.  It makes the
-- complete gateway path testable while retaining its explicit synthetic origin.
INSERT INTO rehab_sessions (id, organization_id, episode_id, source_kind, started_at)
VALUES ('synthetic-session-v1', 'org-demo', 'episode-demo', 'synthetic', CURRENT_TIMESTAMP)
ON CONFLICT (id) DO NOTHING;

INSERT INTO exercise_attempts (id, organization_id, rehab_session_id, exercise_prescription_id, started_at)
VALUES (
    'synthetic-attempt-v1', 'org-demo', 'synthetic-session-v1',
    'prescription-heel-slide-demo-v1', CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO sensor_devices (id, organization_id, device_identifier, model)
VALUES
    ('sensor-synthetic-thigh', 'org-demo', 'synthetic-thigh', 'synthetic'),
    ('sensor-synthetic-shank', 'org-demo', 'synthetic-shank', 'synthetic'),
    ('sensor-synthetic-foot', 'org-demo', 'synthetic-foot', 'synthetic')
ON CONFLICT (organization_id, device_identifier) DO NOTHING;
