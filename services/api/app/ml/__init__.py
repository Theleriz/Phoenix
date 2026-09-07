"""Local, in-process movement-interpretation ML (shadow mode).

Stage 9 of IMPLEMENTATION_PLAN.md. This package runs entirely inside the API
process -- there is no separate inference service. It never produces
patient-visible output and never affects score or feedback until a checkpoint
is validated and clinically approved.

Data flow (called from ``app.main.ingest_imu_packet``):

    raw gateway packets
        -> app.signal_quality.evaluate_signal_quality   (gate)
        -> app.preprocessing.preprocess_transport_events (resample -> frames)
        -> ml.input.build_model_input                    (frames -> (T, 3, 9) tensor)
        -> ml.inference.run_shadow_inference             (gate + model or abstain)
        -> shadow_predictions table                      (audit only)

The trained model file is NOT committed. Drop it into ``ml/checkpoints/``
(see ``ml/checkpoints/README.md``); until then every call abstains.
"""

from __future__ import annotations

from .inference import run_shadow_inference

__all__ = ["run_shadow_inference"]
