"""Offline tests for the generic ROSBridge transport.

Run from repository root:
    python -m unittest framework.test_files.test_rosbridge_client
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)

from framework.communication.transport.rosbridge import ROSBridgeClient


class TestROSBridgeClient(unittest.TestCase):

    def setUp(self):
        self.ros_patcher = patch(
            "framework.communication.transport.rosbridge.client"
            ".roslibpy.Ros"
        )
        self.topic_patcher = patch(
            "framework.communication.transport.rosbridge.client"
            ".roslibpy.Topic"
        )

        self.mock_ros_class = self.ros_patcher.start()
        self.mock_topic_class = self.topic_patcher.start()

        self.addCleanup(self.ros_patcher.stop)
        self.addCleanup(self.topic_patcher.stop)

        self.mock_ros = MagicMock()
        self.mock_ros.is_connected = True
        self.mock_ros_class.return_value = self.mock_ros

        self.mock_topic = MagicMock()
        self.mock_topic.message_type = "std_msgs/String"
        self.mock_topic_class.return_value = self.mock_topic

        self.client = ROSBridgeClient(
            host="127.0.0.1",
            port=9090,
        )

    def tearDown(self):
        self.client.close()

    def test_connect(self):
        self.client.connect()

        self.mock_ros_class.assert_called_once_with(
            host="127.0.0.1",
            port=9090,
        )
        self.mock_ros.run.assert_called_once_with(
            timeout=5.0
        )
        self.assertTrue(self.client.connected)

    def test_publish(self):
        self.client.connect()

        self.client.publish(
            "/test",
            "std_msgs/String",
            {"data": "hello"},
        )

        self.mock_topic_class.assert_called_once()
        self.mock_topic.advertise.assert_called_once()
        self.mock_topic.publish.assert_called_once()

    def test_reuse_publisher(self):
        self.client.connect()

        for value in range(3):
            self.client.publish(
                "/test",
                "std_msgs/String",
                {"data": str(value)},
            )

        self.assertEqual(
            self.mock_topic_class.call_count,
            1,
        )
        self.assertEqual(
            self.mock_topic.publish.call_count,
            3,
        )

    def test_subscribe_and_unsubscribe(self):
        self.client.connect()

        callback = MagicMock()

        self.client.subscribe(
            "/feedback",
            "std_msgs/String",
            callback,
        )

        self.mock_topic.subscribe.assert_called_once_with(
            callback
        )

        self.client.unsubscribe("/feedback")

        self.mock_topic.unsubscribe.assert_called_once()

    def test_disconnected_publish_rejected(self):
        self.client.connect()
        self.mock_ros.is_connected = False

        with self.assertRaises(ConnectionError):
            self.client.publish(
                "/test",
                "std_msgs/String",
                {"data": "hello"},
            )

        self.mock_topic.publish.assert_not_called()

    def test_initial_connection_failure(self):
        self.mock_ros.run.side_effect = TimeoutError(
            "Connection timeout"
        )

        with self.assertRaises(TimeoutError):
            self.client.connect()

        with self.assertRaises(RuntimeError):
            self.client.connect()

    def test_close_is_idempotent(self):
        self.client.connect()
        self.client.close()
        self.client.close()

        self.mock_ros.close.assert_called_once()

    def test_invalid_message(self):
        self.client.connect()

        with self.assertRaises(TypeError):
            self.client.publish(
                "/test",
                "std_msgs/String",
                "not a dictionary",
            )


if __name__ == "__main__":
    unittest.main()