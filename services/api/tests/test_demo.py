import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.demo import demo_snapshot


class DemoSnapshotTests(unittest.TestCase):
    def test_replay_fixture_is_explicitly_synthetic(self) -> None:
        replay = demo_snapshot()["replay_session"]

        self.assertEqual(replay["origin"], "synthetic")
        self.assertEqual(replay["validation_status"], "synthetic")
        self.assertEqual(replay["sensor_roles"], ["thigh", "shank", "foot"])

    def test_patients_queue_has_valid_statuses(self) -> None:
        patients = demo_snapshot()["patients"]

        self.assertTrue(len(patients) >= 2)
        for patient in patients:
            self.assertIn(patient["status"], {"stable", "review", "urgent"})
            self.assertIn(patient["rom_trend"], {"up", "flat", "down"})

    def test_snapshot_is_a_fresh_copy(self) -> None:
        first = demo_snapshot()
        first["patients"].clear()

        self.assertTrue(len(demo_snapshot()["patients"]) > 0)


if __name__ == "__main__":
    unittest.main()
