-- Stage 7: versioned, technical-only stream-quality evaluation.
-- No score, rep count, ROM, feedback, or clinical decision is introduced here.

INSERT INTO algorithm_versions (id, organization_id, name, code_reference, parameters)
VALUES (
    'algorithm-signal-quality-v1', 'org-demo', 'gateway_signal_quality',
    'services/api/app/signal_quality.py@v1',
    '{"scope":"technical_only","minimum_calibration_seconds":3,"minimum_sample_rate_hz":15,"maximum_sync_skew_ms":100,"maximum_gap_seconds":1,"clipping_raw_limit":32700,"maximum_static_gyroscope_raw":100}'::jsonb
)
ON CONFLICT (organization_id, name, code_reference) DO NOTHING;
