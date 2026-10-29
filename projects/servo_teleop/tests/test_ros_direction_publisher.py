"""Unit tests for direction-only ROSBridge publication.

Run: python -m unittest projects.servo_teleop.tests.test_ros_direction_publisher
"""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.servo_teleop.operations.ros_direction_publisher import (
    ROSDirectionPublisher,
)


class TestROSDirectionPublisher(unittest.TestCase):
    def setUp(self):
        self.bridge = MagicMock()
        self.bridge.connected = True
        self.publisher = ROSDirectionPublisher(client=self.bridge)

    def test_connect_and_advertise(self):
        self.publisher.connect()
        self.bridge.connect.assert_called_once_with()
        self.bridge.advertise.assert_called_once_with(
            "/gh_servo/directions", "std_msgs/Int8MultiArray"
        )

    def test_direction_order_preserved(self):
        self.publisher.publish([1, 0, -1], [0, 1, -1])
        self.bridge.publish.assert_called_once_with(
            "/gh_servo/directions", "std_msgs/Int8MultiArray",
            {"data": [1, 0, -1, 0, 1, -1]},
        )

    def test_zero(self):
        self.publisher.zero()
        self.assertEqual(self.bridge.publish.call_args.args[2],
                         {"data": [0, 0, 0, 0, 0, 0]})

    def test_reject_invalid_axes(self):
        for linear, angular in (
            ([2, 0, 0], [0, 0, 0]),
            ([1.0, 0, 0], [0, 0, 0]),
            ([True, 0, 0], [0, 0, 0]),
            ([0, 0], [0, 0, 0]),
        ):
            with self.subTest(linear=linear, angular=angular):
                with self.assertRaises(ValueError):
                    self.publisher.publish(linear, angular)
        self.bridge.publish.assert_not_called()

    def test_close(self):
        self.publisher.close()
        self.bridge.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
