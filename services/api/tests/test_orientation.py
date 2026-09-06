import sys
import unittest
from math import isclose
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.orientation import Quaternion, calibrated_relative_orientation, from_euler_degrees


class OrientationTests(unittest.TestCase):
    def test_euler_conversion_produces_a_unit_quaternion(self) -> None:
        result = from_euler_degrees(0.0, 90.0, 0.0)
        self.assertTrue(isclose(result.w**2 + result.x**2 + result.y**2 + result.z**2, 1.0))

    def test_identical_baseline_and_current_orientation_is_identity(self) -> None:
        identity = from_euler_degrees(0.0, 0.0, 0.0)
        result = calibrated_relative_orientation(
            proximal_current=identity,
            distal_current=identity,
            proximal_baseline=identity,
            distal_baseline=identity,
        )
        self.assertEqual(result, Quaternion(1.0, 0.0, 0.0, 0.0))

    def test_relative_orientation_uses_each_sensor_baseline(self) -> None:
        identity = from_euler_degrees(0.0, 0.0, 0.0)
        distal_current = from_euler_degrees(0.0, 90.0, 0.0)
        result = calibrated_relative_orientation(
            proximal_current=identity,
            distal_current=distal_current,
            proximal_baseline=identity,
            distal_baseline=identity,
        )
        self.assertTrue(isclose(result.y, distal_current.y))
