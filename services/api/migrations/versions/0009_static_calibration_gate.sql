-- Stage 7: auditable confirmation of a technically valid static window.
-- This is not an orientation, anatomical, or clinical calibration.

INSERT INTO algorithm_versions (id, organization_id, name, code_reference, parameters)
VALUES (
    'algorithm-static-calibration-gate-v1', 'org-demo', 'static_calibration_gate',
    'services/api/app/signal_quality.py@v1',
    '{"scope":"technical_only","required_signal_quality":"HIGH","minimum_duration_seconds":3,"maximum_duration_seconds":5}'::jsonb
)
ON CONFLICT (organization_id, name, code_reference) DO NOTHING;
