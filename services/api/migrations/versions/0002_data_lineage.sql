-- Stage 3: versioned, tenant-scoped clinical data lineage.
-- Raw packets, scores and clinician actions are append-only.

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE clinics (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (name IN (
        'patient', 'clinician', 'rehabilitologist', 'organization_admin',
        'research_viewer', 'technical_admin'
    ))
);

CREATE TABLE memberships (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    role_id TEXT NOT NULL REFERENCES roles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, user_id, role_id)
);

ALTER TABLE clinicians ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users(id);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS clinic_id TEXT REFERENCES clinics(id);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS external_reference TEXT;

CREATE TABLE episodes_of_care (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    patient_id TEXT NOT NULL REFERENCES patients(id),
    clinic_id TEXT REFERENCES clinics(id),
    operated_side TEXT NOT NULL CHECK (operated_side IN ('left', 'right')),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE surgeries (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    episode_id TEXT NOT NULL REFERENCES episodes_of_care(id),
    procedure_name TEXT NOT NULL,
    performed_on DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE protocol_assignments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    episode_id TEXT NOT NULL REFERENCES episodes_of_care(id),
    protocol_template_id TEXT NOT NULL REFERENCES protocol_templates(id),
    version INTEGER NOT NULL CHECK (version > 0),
    assigned_by_clinician_id TEXT REFERENCES clinicians(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (episode_id, version)
);

CREATE TABLE exercise_definitions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    definition_version INTEGER NOT NULL CHECK (definition_version > 0),
    configuration JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, name, definition_version)
);

CREATE TABLE exercise_prescriptions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    protocol_assignment_id TEXT NOT NULL REFERENCES protocol_assignments(id),
    exercise_definition_id TEXT NOT NULL REFERENCES exercise_definitions(id),
    configuration JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sensor_devices (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    device_identifier TEXT NOT NULL,
    model TEXT,
    adapter_configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, device_identifier)
);

CREATE TABLE calibrations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    episode_id TEXT NOT NULL REFERENCES episodes_of_care(id),
    parameters JSONB NOT NULL,
    algorithm_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rehab_sessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    episode_id TEXT NOT NULL REFERENCES episodes_of_care(id),
    calibration_id TEXT REFERENCES calibrations(id),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('synthetic', 'hardware')),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE exercise_attempts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    rehab_session_id TEXT NOT NULL REFERENCES rehab_sessions(id),
    exercise_prescription_id TEXT REFERENCES exercise_prescriptions(id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE raw_imu_chunks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    exercise_attempt_id TEXT NOT NULL REFERENCES exercise_attempts(id),
    sensor_device_id TEXT REFERENCES sensor_devices(id),
    storage_uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    packet_count INTEGER NOT NULL CHECK (packet_count >= 0),
    validation_status TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE algorithm_versions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    code_reference TEXT NOT NULL,
    parameters JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, name, code_reference)
);

CREATE TABLE derived_metrics (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    exercise_attempt_id TEXT NOT NULL REFERENCES exercise_attempts(id),
    raw_imu_chunk_id TEXT REFERENCES raw_imu_chunks(id),
    calibration_id TEXT REFERENCES calibrations(id),
    algorithm_version_id TEXT NOT NULL REFERENCES algorithm_versions(id),
    name TEXT NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE signal_quality (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    exercise_attempt_id TEXT NOT NULL REFERENCES exercise_attempts(id),
    raw_imu_chunk_id TEXT REFERENCES raw_imu_chunks(id),
    algorithm_version_id TEXT NOT NULL REFERENCES algorithm_versions(id),
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE score_versions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    formula JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, name)
);

CREATE TABLE exercise_scores (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    exercise_attempt_id TEXT NOT NULL REFERENCES exercise_attempts(id),
    score_version_id TEXT NOT NULL REFERENCES score_versions(id),
    algorithm_version_id TEXT NOT NULL REFERENCES algorithm_versions(id),
    calibration_id TEXT REFERENCES calibrations(id),
    value JSONB NOT NULL,
    calculation_reason TEXT NOT NULL,
    recalculated_from_score_id TEXT REFERENCES exercise_scores(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE prom_responses (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    episode_id TEXT NOT NULL REFERENCES episodes_of_care(id),
    rehab_session_id TEXT REFERENCES rehab_sessions(id),
    answers JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE symptom_checks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    rehab_session_id TEXT NOT NULL REFERENCES rehab_sessions(id),
    answers JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alerts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    episode_id TEXT NOT NULL REFERENCES episodes_of_care(id),
    severity TEXT NOT NULL CHECK (severity IN ('green', 'yellow', 'red')),
    rule_version TEXT NOT NULL,
    trigger JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE clinician_actions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    alert_id TEXT REFERENCES alerts(id),
    clinician_id TEXT REFERENCES clinicians(id),
    action_type TEXT NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    episode_id TEXT NOT NULL REFERENCES episodes_of_care(id),
    sender_user_id TEXT REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE prompt_versions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    template TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, name)
);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    actor_user_id TEXT REFERENCES users(id),
    event_type TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION prevent_immutable_change() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '% records are append-only', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER raw_imu_chunks_immutable
    BEFORE UPDATE OR DELETE ON raw_imu_chunks
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();
CREATE TRIGGER exercise_scores_immutable
    BEFORE UPDATE OR DELETE ON exercise_scores
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();
CREATE TRIGGER clinician_actions_immutable
    BEFORE UPDATE OR DELETE ON clinician_actions
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();

CREATE INDEX idx_episodes_organization_patient ON episodes_of_care (organization_id, patient_id);
CREATE INDEX idx_sessions_organization_episode ON rehab_sessions (organization_id, episode_id);
CREATE INDEX idx_attempts_organization_session ON exercise_attempts (organization_id, rehab_session_id);
CREATE INDEX idx_raw_chunks_organization_attempt ON raw_imu_chunks (organization_id, exercise_attempt_id);
CREATE INDEX idx_metrics_organization_attempt ON derived_metrics (organization_id, exercise_attempt_id);
CREATE INDEX idx_scores_organization_attempt ON exercise_scores (organization_id, exercise_attempt_id);
CREATE INDEX idx_alerts_organization_episode ON alerts (organization_id, episode_id);
