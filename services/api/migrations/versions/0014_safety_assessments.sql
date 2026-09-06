-- Stage 14: durable, append-only record of every deterministic safety
-- evaluation of a post-session symptom check -- including GREEN and withheld
-- outcomes that never create an alert.
--
-- Without this table the only persisted evidence of a triage run was the
-- alert row, so GREEN / withheld results left no lineage at all and a later
-- re-evaluation could not be told apart from the original. Each row links a
-- symptom check to the exact policy version it was scored against.

CREATE TABLE safety_assessments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    rehab_session_id TEXT NOT NULL REFERENCES rehab_sessions(id),
    symptom_check_id TEXT NOT NULL REFERENCES symptom_checks(id),
    status TEXT NOT NULL CHECK (status IN ('evaluated', 'withheld')),
    level TEXT CHECK (level IN ('GREEN', 'YELLOW', 'RED')),
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_version TEXT,
    alert_id TEXT REFERENCES alerts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- A withheld assessment never carries a severity level or an alert.
    CHECK (status <> 'withheld' OR (level IS NULL AND alert_id IS NULL)),
    -- Only YELLOW / RED may reference an alert.
    CHECK (alert_id IS NULL OR level IN ('YELLOW', 'RED'))
);

CREATE INDEX idx_safety_assessments_session
    ON safety_assessments (rehab_session_id, created_at DESC);

CREATE INDEX idx_safety_assessments_symptom_check
    ON safety_assessments (symptom_check_id);

CREATE TRIGGER safety_assessments_immutable
    BEFORE UPDATE OR DELETE ON safety_assessments
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();
