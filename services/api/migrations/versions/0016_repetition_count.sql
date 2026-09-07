-- Stage 8/10: deterministic repetition segmentation for the patient rep counter.
-- The primary rep signal; a trained model's rep boundaries stay shadow-only.

INSERT INTO algorithm_versions (id, organization_id, name, code_reference, parameters)
VALUES (
    'algorithm-repetition-count-v1', 'org-demo', 'deterministic_repetition_count',
    'services/api/app/reps.py@v1',
    '{"proxy":"shank_minus_thigh_ori_pitch_deg","enter_flexion_deg":18.0,"exit_flexion_deg":7.0,'
    '"min_rep_frames":5,"clinical_scoring":false,'
    '"limitations":["Engineering thresholds, not a clinically approved valid-repetition definition."]}'::jsonb
)
ON CONFLICT (organization_id, name, code_reference) DO NOTHING;
