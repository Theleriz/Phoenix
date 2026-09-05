-- Stage 5: versioned protocol configuration. No clinical thresholds are seeded.

ALTER TABLE protocol_templates ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE protocol_templates ADD COLUMN IF NOT EXISTS configuration JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE protocol_templates ADD COLUMN IF NOT EXISTS approval_state TEXT NOT NULL DEFAULT 'draft'
    CHECK (approval_state IN ('draft', 'clinically_approved', 'retired'));
ALTER TABLE protocol_assignments ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_protocol_assignments_current
    ON protocol_assignments (organization_id, episode_id, version DESC);

INSERT INTO memberships (id, organization_id, user_id, role_id) VALUES
    ('membership-clinician-role-demo', 'org-demo', 'user-clinician-demo', 'role-clinician')
ON CONFLICT (organization_id, user_id, role_id) DO NOTHING;

INSERT INTO episodes_of_care (id, organization_id, patient_id, operated_side, status)
VALUES ('episode-demo', 'org-demo', 'patient-demo', 'left', 'development_fixture')
ON CONFLICT (id) DO NOTHING;

INSERT INTO protocol_templates (id, organization_id, name, is_synthetic, version, configuration, approval_state)
VALUES (
    'protocol-tka-foundation-v1',
    'org-demo',
    'TKA foundation — draft',
    TRUE,
    1,
    '{"restriction_priority":["individual_clinician","clinic_or_surgeon_template","phoenix_base_template"],"clinical_approval_required":true}'::jsonb,
    'draft'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO exercise_definitions (id, organization_id, name, definition_version, configuration)
VALUES (
    'exercise-heel-slide-v1',
    'org-demo',
    'Heel Slide',
    1,
    '{
      "approval_state":"draft",
      "required_sensors":["thigh","shank","foot"],
      "position":null,
      "reference_video":null,
      "instructions":{},
      "primary_metrics":[],
      "secondary_metrics":[],
      "prescription_schema":["sets","repetitions","frequency","target_rom_degrees","tempo","hold_seconds"],
      "valid_repetition_definition":null,
      "stop_conditions":[],
      "live_feedback_whitelist":[],
      "scoring_formula":null,
      "limitations":["No clinical targets, repetition algorithm, scoring formula or stop conditions are approved in this development fixture."]
    }'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO protocol_assignments (
    id, organization_id, episode_id, protocol_template_id, version, assigned_by_clinician_id
)
VALUES (
    'protocol-assignment-demo-v1', 'org-demo', 'episode-demo',
    'protocol-tka-foundation-v1', 1, 'clinician-demo'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO exercise_prescriptions (
    id, organization_id, protocol_assignment_id, exercise_definition_id, configuration
)
VALUES (
    'prescription-heel-slide-demo-v1', 'org-demo', 'protocol-assignment-demo-v1',
    'exercise-heel-slide-v1',
    '{"approval_state":"draft","sets":null,"repetitions":null,"frequency":null,"target_rom_degrees":null,"tempo":null,"hold_seconds":null,"restriction_sources":[]}'::jsonb
)
ON CONFLICT (id) DO NOTHING;