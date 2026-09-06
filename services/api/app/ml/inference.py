"""Shadow-mode movement-interpretation inference.

Called once per (re)processed session from ``app.main.ingest_imu_packet``,
after transport preprocessing. Output is written to ``shadow_predictions`` for
audit only -- never patient-visible, never affecting score or feedback
(Stage 9 of IMPLEMENTATION_PLAN.md). With no validated checkpoint present it
abstains, which is the expected state until the model is downloaded and
approved.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

from .input import build_model_input, sliding_windows, to_limu_units
from .model import ModelBundle, load_model_bundle
from .shadow import ShadowStatus, shadow_infer

MODEL_VERSION_WHEN_ABSENT = "movement-interpretation-unloaded"
FEATURE_VERSIONS_WHEN_ABSENT = ("imu_transport_preprocessing", "model_input_tsc_9ch_v1")


@lru_cache(maxsize=1)
def _bundle() -> ModelBundle | None:
    return load_model_bundle()


def reset_model_cache() -> None:
    """Drop the cached checkpoint so a newly added model is picked up."""
    _bundle.cache_clear()


LIMU_ACC_NORM = 9.8  # upstream Preprocess4Normalization divides accel by this


def _apply_normalization(batch: np.ndarray, normalization: dict[str, Any]) -> np.ndarray:
    kind = normalization.get("kind")
    if kind == "zscore":
        mean = np.asarray(normalization.get("mean", 0.0), dtype=np.float32)
        std = np.asarray(normalization.get("std", 1.0), dtype=np.float32)
        return (batch - mean) / np.where(std == 0, 1.0, std)
    if kind == "scale":
        return batch * np.asarray(normalization.get("factor", 1.0), dtype=np.float32)
    if kind == "limu":
        # Mirrors utils.Preprocess4Normalization(feature_num=6): accel / 9.8,
        # gyro untouched. Applied to the last axis (channels), accel = [0:3].
        out = np.array(batch, dtype=np.float32, copy=True)
        out[..., 0:3] /= LIMU_ACC_NORM
        return out
    return batch


def _to_layout(batch_ntsc: np.ndarray, layout: str) -> np.ndarray:
    """``batch_ntsc`` is ``(N, T, S, C)``; reshape to what the model wants."""
    key = layout.upper().replace(" ", "")
    count, steps, sensors, channels = batch_ntsc.shape
    if key in ("N,T,S,C", "NTSC"):
        return batch_ntsc
    if key in ("N,S,T,C", "NSTC"):
        return batch_ntsc.transpose(0, 2, 1, 3)
    if key in ("N,T,SC", "N,T,S*C"):
        return batch_ntsc.reshape(count, steps, sensors * channels)
    if key in ("N,S,TC", "N,S,T*C"):
        return batch_ntsc.transpose(0, 2, 1, 3).reshape(count, sensors, steps * channels)
    return batch_ntsc


def run_shadow_inference(
    frames: list[dict[str, Any]], signal_quality: dict[str, Any]
) -> dict[str, Any]:
    """Return a JSON-safe shadow-prediction dict for one processed session."""
    bundle = _bundle()
    model_version = bundle.meta.model_version if bundle else MODEL_VERSION_WHEN_ABSENT
    feature_versions = (
        list(bundle.meta.feature_versions)
        if bundle and bundle.meta.feature_versions
        else list(FEATURE_VERSIONS_WHEN_ABSENT)
    )

    model_input = build_model_input(frames)
    gate = shadow_infer(
        signal_quality=signal_quality,
        model_version=model_version,
        feature_versions=feature_versions,
        model_available=bundle is not None and not model_input.dropped,
    )
    result: dict[str, Any] = {
        **gate.as_dict(),
        "input_frames": model_input.n_frames,
        "input_shape": list(model_input.tensor.shape),
        "input_dropped": model_input.dropped,
    }
    if gate.status is ShadowStatus.ABSTAINED or bundle is None:
        return result

    window = bundle.meta.window_samples
    stride = max(1, window // 2)
    windows = sliding_windows(model_input.tensor, window, stride)  # (N, W, S, C)
    if windows.shape[0] == 0:
        result["status"] = ShadowStatus.ABSTAINED.value
        result["reason"] = "not_enough_frames_for_one_window"
        return result

    if bundle.load_report:
        result["load_report"] = bundle.load_report
    try:
        if bundle.meta.framework == "limu_bert":
            embedding, extra = _run_limu_bert(bundle, windows)
        else:
            embedding, extra = _run_generic(bundle, windows)
    except Exception as error:  # pragma: no cover - depends on the downloaded model
        result["status"] = ShadowStatus.ABSTAINED.value
        result["reason"] = f"model_runtime_error:{type(error).__name__}"
        return result

    result.update(
        {
            "status": ShadowStatus.PREDICTED.value,
            "reason": None,
            "windows": int(windows.shape[0]),
            "window_samples": window,
            "stride_samples": stride,
            # An embedding, not a label or score: interpretation waits on the
            # trained head and clinical approval.
            "embedding": embedding,
            **extra,
        }
    )
    return result


def _run_generic(bundle: ModelBundle, windows: np.ndarray) -> tuple[list[float], dict[str, Any]]:
    batch = _apply_normalization(windows, bundle.meta.normalization)
    batch = _to_layout(batch, bundle.meta.input_layout)
    output = np.asarray(
        bundle.runner(np.ascontiguousarray(batch, dtype=np.float32)), dtype=np.float32
    )
    pooled = output.reshape(output.shape[0], -1).mean(axis=0)
    return pooled.tolist(), {"output_shape": list(output.shape)}


def _run_limu_bert(
    bundle: ModelBundle, windows: np.ndarray
) -> tuple[list[float], dict[str, Any]]:
    """One encoder call per sensor on accel+gyro (6ch); fuse across sensors.

    windows: (N, W, S, C) in g / deg-per-s / degrees. LIMU-BERT has no
    multi-sensor concept and no magnetometer, so orientation channels are
    dropped here and used by the deterministic branch instead.
    """
    limu_windows = to_limu_units(windows)  # accel m/s^2, gyro rad/s
    limu_windows = _apply_normalization(limu_windows, {"kind": "limu"})
    n_sensors = windows.shape[2]
    per_sensor: list[np.ndarray] = []
    for sensor_index in range(n_sensors):
        batch = np.ascontiguousarray(limu_windows[:, :, sensor_index, 0:6], dtype=np.float32)
        hidden = np.asarray(bundle.runner(batch), dtype=np.float32)  # (N, W, hidden)
        per_sensor.append(hidden.mean(axis=1))  # (N, hidden) mean over time
    fused = np.concatenate(per_sensor, axis=1)  # (N, hidden * n_sensors)
    pooled = fused.mean(axis=0)  # (hidden * n_sensors,) mean over windows
    return pooled.tolist(), {
        "fusion": "per_sensor_meanpool_concat",
        "sensors": list(bundle.meta.sensor_order) or n_sensors,
        "embedding_dim": int(fused.shape[1]),
        "per_sensor_hidden": int(per_sensor[0].shape[1]),
    }
