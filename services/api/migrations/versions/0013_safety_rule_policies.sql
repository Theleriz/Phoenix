-- Stage 13: versioned, organization-scoped safety triage policy.
-- Never overwritten: a new configuration is a new row, never an UPDATE.
-- No policy is clinically_approved yet, so no real alert can be generated
-- until a clinician explicitly approves one (see app/safety_rules.py).

CREATE TABLE safety_rule_policies (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    version TEXT NOT NULL,
    configuration JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, version)
);

CREATE TRIGGER safety_rule_policies_immutable
    BEFORE UPDATE OR DELETE ON safety_rule_policies
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();

CREATE INDEX idx_safety_rule_policies_latest
    ON safety_rule_policies (organization_id, created_at DESC);

INSERT INTO safety_rule_policies (id, organization_id, version, configuration) VALUES (
    'safety-policy-org-demo-v1',
    'org-demo',
    'org-demo-safety-v1',
    '{
      "approval_state": "draft",
      "red_symptom_keys": ["chest_pain", "shortness_of_breath", "calf_pain"],
      "yellow_symptom_keys": ["swelling", "redness", "drainage", "dizziness"],
      "pain_increase_yellow_threshold": 3,
      "limitations": ["Draft; clinical review required before any alert is generated."]
    }'::jsonb
)
ON CONFLICT (organization_id, version) DO NOTHING;
