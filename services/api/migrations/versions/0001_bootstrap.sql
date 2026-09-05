-- Development bootstrap only. Clinical schema and data lineage arrive in stage 3.
CREATE TABLE organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE clinicians (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    display_name TEXT NOT NULL
);

CREATE TABLE patients (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    display_name TEXT NOT NULL,
    post_op_day INTEGER NOT NULL CHECK (post_op_day >= 0)
);

CREATE TABLE protocol_templates (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE imu_replay_sessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    patient_id TEXT NOT NULL REFERENCES patients(id),
    origin TEXT NOT NULL CHECK (origin IN ('synthetic', 'hardware')),
    validation_status TEXT NOT NULL,
    frame_count INTEGER NOT NULL CHECK (frame_count >= 0)
);

INSERT INTO organizations (id, name) VALUES ('org-demo', 'PHOENIX Demo Clinic');
INSERT INTO clinicians (id, organization_id, display_name) VALUES ('clinician-demo', 'org-demo', 'Демо-врач');
INSERT INTO patients (id, organization_id, display_name, post_op_day) VALUES ('patient-demo', 'org-demo', 'Демо-пациент', 14);
INSERT INTO protocol_templates (id, organization_id, name, is_synthetic) VALUES ('protocol-demo', 'org-demo', 'Synthetic replay only', TRUE);
INSERT INTO imu_replay_sessions (id, organization_id, patient_id, origin, validation_status, frame_count)
VALUES ('synthetic-session-v1', 'org-demo', 'patient-demo', 'synthetic', 'synthetic', 15);
