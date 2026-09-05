-- NTZ v1.2: structured MVP scope for adult unilateral primary TKA.
-- Values are clinician-entered context, not automatic clinical recommendations.

ALTER TABLE patients ADD COLUMN IF NOT EXISTS date_of_birth DATE;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS sex_for_analytics TEXT
    CHECK (sex_for_analytics IN ('female', 'male', 'intersex', 'not_recorded'));

ALTER TABLE episodes_of_care ADD COLUMN IF NOT EXISTS procedure_kind TEXT
    NOT NULL DEFAULT 'primary_tka'
    CHECK (procedure_kind = 'primary_tka');
ALTER TABLE episodes_of_care ADD COLUMN IF NOT EXISTS pathway_mode TEXT
    NOT NULL DEFAULT 'standard'
    CHECK (pathway_mode IN ('standard', 'clinician_managed'));
ALTER TABLE episodes_of_care ADD COLUMN IF NOT EXISTS weight_bearing_status TEXT;
ALTER TABLE episodes_of_care ADD COLUMN IF NOT EXISTS precautions JSONB
    NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE episodes_of_care ADD COLUMN IF NOT EXISTS next_visit_at TIMESTAMPTZ;

CREATE INDEX idx_episodes_mvp_scope
    ON episodes_of_care (organization_id, procedure_kind, pathway_mode);
