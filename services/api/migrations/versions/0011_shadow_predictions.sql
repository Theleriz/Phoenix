-- Stage 9: ML output is retained only in shadow mode until clinical approval.

CREATE TABLE shadow_predictions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    exercise_attempt_id TEXT NOT NULL REFERENCES exercise_attempts(id),
    raw_imu_chunk_id TEXT REFERENCES raw_imu_chunks(id),
    algorithm_version_id TEXT NOT NULL REFERENCES algorithm_versions(id),
    prediction JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shadow_predictions_attempt
    ON shadow_predictions (organization_id, exercise_attempt_id, created_at DESC);

CREATE TRIGGER shadow_predictions_immutable
    BEFORE UPDATE OR DELETE ON shadow_predictions
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();

INSERT INTO algorithm_versions (id, organization_id, name, code_reference, parameters)
VALUES (
    'algorithm-shadow-inference-v1', 'org-demo', 'shadow_inference_gate',
    'services/biomechanics/shadow.py@v1',
    '{"mode":"shadow","patient_visible":false,"affects_score":false,"affects_feedback":false,"required_feature_versions":["imu_transport_preprocessing"]}'::jsonb
)
ON CONFLICT (organization_id, name, code_reference) DO NOTHING;
