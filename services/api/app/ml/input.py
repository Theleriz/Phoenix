"""Turn preprocessed transport frames into the model input tensor.

Pure and deterministic; no model dependency. Everything downstream calls
``build_model_input`` and never touches raw frames directly.

Tensor shape ``(T, 3, 9)`` float32:
  axis 1 (sensors)  -> preprocessing.REQUIRED_ROLES  == (thigh, shank, foot)
  axis 2 (channels) -> preprocessing.CHANNELS
      ax ay az   accelerometer, converted to g
      gx gy gz   gyroscope, converted to deg/s
      ori_roll ori_pitch ori_yaw   device orientation, degrees (unchanged)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ..preprocessing import CHANNELS, REQUIRED_ROLES

# WT901BLE68 datasheet full scale over int16.
#   accel: VERIFIED against real captures -- resting |a| ~ 2048 LSB ~ 1 g.
#   gyro : ASSUMED (+/-2000 deg/s); not bench-verified. See
#          docs/imu/current-script-audit.md.
ACCEL_G_PER_LSB = 16.0 / 32768.0
GYRO_DPS_PER_LSB = 2000.0 / 32768.0

_ACCEL = ("ax", "ay", "az")
_GYRO = ("gx", "gy", "gz")

_G_TO_MS2 = 9.80665
_DEG_TO_RAD = np.pi / 180.0


def to_limu_units(tensor: np.ndarray) -> np.ndarray:
    """``(..., 9)`` in g / deg-per-s / degrees -> LIMU-BERT's expected units.

    LIMU-BERT's ``Preprocess4Normalization`` divides accel by 9.8 (so it wants
    m/s^2) and leaves gyro untouched (its training data is rad/s, magnitude
    ~+/-10). Orientation channels (6:9) are left as degrees -- the LIMU path
    uses only channels 0:6.
    """
    out = np.array(tensor, dtype=np.float32, copy=True)
    out[..., 0:3] *= _G_TO_MS2
    out[..., 3:6] *= _DEG_TO_RAD
    return out


@dataclass(frozen=True, slots=True)
class ModelInput:
    tensor: np.ndarray  # (T, 3, 9) float32, physical units
    channels: tuple[str, ...]
    sensor_order: tuple[str, ...]
    frame_flags: list[dict[str, Any]]
    dropped: bool  # True when there are no usable frames

    @property
    def n_frames(self) -> int:
        return int(self.tensor.shape[0])


def frames_to_tensor(frames: list[dict[str, Any]]) -> np.ndarray:
    tensor = np.zeros((len(frames), len(REQUIRED_ROLES), len(CHANNELS)), dtype=np.float32)
    for t_index, frame in enumerate(frames):
        for s_index, role in enumerate(REQUIRED_ROLES):
            sensor = frame["sensors"][role]
            for c_index, channel in enumerate(CHANNELS):
                value = float(sensor[channel])
                if channel in _ACCEL:
                    value *= ACCEL_G_PER_LSB
                elif channel in _GYRO:
                    value *= GYRO_DPS_PER_LSB
                tensor[t_index, s_index, c_index] = value
    return tensor


def build_model_input(
    frames: list[dict[str, Any]], *, drop_flagged_frames: bool = False
) -> ModelInput:
    """Convert preprocessing frames to a physical-unit ``(T, 3, 9)`` tensor.

    ``drop_flagged_frames`` removes frames the preprocessor reconstructed across
    a dropout or that saturated at the ADC. Off by default so the caller keeps
    a contiguous time base and can decide per window.
    """
    frames = list(frames)
    flags = [frame.get("flags", {}) for frame in frames]
    if drop_flagged_frames:
        keep = [
            index
            for index, flag in enumerate(flags)
            if not flag.get("interpolated_over_gap") and not flag.get("near_full_scale")
        ]
        frames = [frames[index] for index in keep]
        flags = [flags[index] for index in keep]
    if not frames:
        return ModelInput(
            np.zeros((0, len(REQUIRED_ROLES), len(CHANNELS)), dtype=np.float32),
            CHANNELS,
            REQUIRED_ROLES,
            [],
            dropped=True,
        )
    return ModelInput(frames_to_tensor(frames), CHANNELS, REQUIRED_ROLES, flags, dropped=False)


def sliding_windows(tensor: np.ndarray, window: int, stride: int) -> np.ndarray:
    """``(T, 3, 9)`` -> ``(N, window, 3, 9)`` overlapping windows."""
    if window <= 0 or stride <= 0:
        raise ValueError("window and stride must be positive")
    if tensor.shape[0] < window:
        return np.empty((0, window, *tensor.shape[1:]), dtype=tensor.dtype)
    starts = range(0, tensor.shape[0] - window + 1, stride)
    return np.stack([tensor[start : start + window] for start in starts]).astype(np.float32)
