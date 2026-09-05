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


if __name__ == "__main__":
    unittest.main()
