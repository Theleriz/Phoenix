CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users(id);

CREATE TABLE invitations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    email TEXT NOT NULL,
    role_id TEXT NOT NULL REFERENCES roles(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    created_by_user_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO roles (id, name) VALUES
    ('role-patient', 'patient'),
    ('role-clinician', 'clinician'),
    ('role-rehab', 'rehabilitologist'),
    ('role-org-admin', 'organization_admin'),
    ('role-research', 'research_viewer'),
    ('role-tech-admin', 'technical_admin')
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, email, display_name, password_hash) VALUES
    ('user-clinician-demo', 'clinician@example.test', 'Демо-врач', crypt('demo-password', gen_salt('bf'))),
    ('user-patient-demo', 'patient@example.test', 'Демо-пациент', crypt('demo-password', gen_salt('bf')))
ON CONFLICT (id) DO NOTHING;

UPDATE clinicians SET user_id = 'user-clinician-demo' WHERE id = 'clinician-demo';
UPDATE patients SET user_id = 'user-patient-demo' WHERE id = 'patient-demo';
INSERT INTO memberships (id, organization_id, user_id, role_id) VALUES
    ('membership-clinician-demo', 'org-demo', 'user-clinician-demo', 'role-org-admin'),
    ('membership-patient-demo', 'org-demo', 'user-patient-demo', 'role-patient')
ON CONFLICT (organization_id, user_id, role_id) DO NOTHING;


-- A second tenant exists only to exercise server-side tenant isolation in dev.
INSERT INTO organizations (id, name) VALUES ('org-isolated', 'Isolation Test Clinic')
ON CONFLICT (id) DO NOTHING;
INSERT INTO patients (id, organization_id, display_name, post_op_day)
VALUES ('patient-isolated', 'org-isolated', 'Изолированный демо-пациент', 7)
ON CONFLICT (id) DO NOTHING;
