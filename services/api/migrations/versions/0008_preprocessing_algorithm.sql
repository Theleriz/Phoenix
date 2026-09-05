-- Stage 8: technical preprocessing version. It is not a clinical algorithm.

INSERT INTO algorithm_versions (id, organization_id, name, code_reference, parameters)
VALUES (
    'algorithm-imu-preprocessing-v1', 'org-demo', 'imu_transport_preprocessing',
    'services/biomechanics/preprocessing.py@v1',
    '{"scope":"technical_only","target_rate_hz":20,"filter_kind":"centered_moving_average","filter_window_samples":3,"limitations":["No sensor fusion, angle estimation, rep segmentation, ML interpretation, scoring, or clinical feedback."]}'::jsonb
)
ON CONFLICT (organization_id, name, code_reference) DO NOTHING;
