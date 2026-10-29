"""Direction-only ROSBridge publisher for the Servo master.

The ROS-side adapter is responsible for fixed velocities, command frame,
ROS timestamps, and final MoveIt Servo TwistStamped publishing.
"""

from framework.communication.transport.rosbridge import ROSBridgeClient


class ROSDirectionPublisher:
    MESSAGE_TYPE = "std_msgs/Int8MultiArray"
    DEFAULT_TOPIC = "/gh_servo/directions"

    def __init__(self, host="127.0.0.1", port=9090,
                 topic=DEFAULT_TOPIC, timeout=5.0, client=None):
        if not isinstance(topic, str) or not topic.startswith("/"):
            raise ValueError("ROS topic must be an absolute topic name")
        self.topic = topic
        self._client = client if client is not None else ROSBridgeClient(
            host=host, port=port, timeout=timeout
        )

    @property
    def connected(self):
        return self._client.connected

    @staticmethod
    def message(linear, angular):
        axes = list(linear) + list(angular)
        if len(axes) != 6 or any(type(v) is not int or v not in (-1, 0, 1)
                                  for v in axes):
            raise ValueError("Expected six integer directions in {-1, 0, 1}")
        return {"data": axes}

    def connect(self):
        self._client.connect()
        self._client.advertise(self.topic, self.MESSAGE_TYPE)

    def publish(self, linear, angular):
        self._client.publish(
            self.topic, self.MESSAGE_TYPE, self.message(linear, angular)
        )

    def zero(self):
        self.publish((0, 0, 0), (0, 0, 0))

    def close(self):
        self._client.close()
