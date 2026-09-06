"""Quaternion utilities for research-only, calibrated relative orientation."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin, sqrt


@dataclass(frozen=True, slots=True)
class Quaternion:
    w: float
    x: float
    y: float
    z: float

    def normalized(self) -> Quaternion:
        magnitude = sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if magnitude == 0:
            raise ValueError("quaternion cannot have zero magnitude")
        return Quaternion(
            self.w / magnitude,
            self.x / magnitude,
            self.y / magnitude,
            self.z / magnitude,
        )

    def inverse(self) -> Quaternion:
        unit = self.normalized()
        return Quaternion(unit.w, -unit.x, -unit.y, -unit.z)

    def multiply(self, other: Quaternion) -> Quaternion:
        return Quaternion(
            self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z,
            self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y,
            self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x,
            self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w,
        ).normalized()


def from_euler_degrees(roll: float, pitch: float, yaw: float) -> Quaternion:
    """Convert a documented ZYX Euler convention to a unit quaternion.

    This only preserves an adapter's reported orientation for research. It does
    not establish anatomical axes or calculate a knee angle.
    """
    roll_rad, pitch_rad, yaw_rad = map(radians, (roll, pitch, yaw))
    cr, sr = cos(roll_rad / 2), sin(roll_rad / 2)
    cp, sp = cos(pitch_rad / 2), sin(pitch_rad / 2)
    cy, sy = cos(yaw_rad / 2), sin(yaw_rad / 2)
    return Quaternion(
        cy * cp * cr + sy * sp * sr,
        cy * cp * sr - sy * sp * cr,
        cy * sp * cr + sy * cp * sr,
        sy * cp * cr - cy * sp * sr,
    ).normalized()


def calibrated_relative_orientation(
    *,
    proximal_current: Quaternion,
    distal_current: Quaternion,
    proximal_baseline: Quaternion,
    distal_baseline: Quaternion,
) -> Quaternion:
    """Return calibrated distal-vs-proximal orientation, without anatomy claims."""
    proximal_delta = proximal_baseline.inverse().multiply(proximal_current)
    distal_delta = distal_baseline.inverse().multiply(distal_current)
    return proximal_delta.inverse().multiply(distal_delta)
