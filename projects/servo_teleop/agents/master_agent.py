"""Servo teleoperation master, optionally publishing ROSBridge directions.

Offline mode preserves the existing TCP protocol and master state machine.
ROSBridge mode publishes std_msgs/Int8MultiArray direction selectors only.
ROS 2 owns velocity scaling, frame_id, and final TwistStamped generation.
"""

import argparse
from pathlib import Path
import sys
import threading
import time

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.workflow import StreamHandler
from projects.servo_teleop.operations.control_state import ServoControlState
from projects.servo_teleop.operations.ros_direction_publisher import ROSDirectionPublisher

ZERO = (0, 0, 0)


class ServoMaster:
    def __init__(self, host="127.0.0.1", port=9060, command_timeout=0.3,
                 rosbridge=False, ros_host="127.0.0.1", ros_port=9090,
                 ros_topic="/gh_servo/directions", ros_rate=20.0,
                 ros_client=None):
        if ros_rate <= 0:
            raise ValueError("ros_rate must be positive")

        self.state = ServoControlState(command_timeout=command_timeout)
        self.handler = StreamHandler(
            host=host, port=port, on_message=self._on_message
        )
        self._running = threading.Event()
        self._monitor_thread = None
        self._publisher_thread = None
        self._ros_period = 1.0 / float(ros_rate)
        self._ros_fault = None
        self._ros_lock = threading.RLock()
        self._ros = None

        if rosbridge:
            self._ros = ROSDirectionPublisher(
                host=ros_host, port=ros_port, topic=ros_topic,
                client=ros_client,
            )

    def _ros_ready(self):
        with self._ros_lock:
            return self._ros_fault is None and (
                self._ros is None or self._ros.connected
            )

    def _fault_ros(self, reason):
        with self._ros_lock:
            if self._ros_fault is not None:
                return
            self._ros_fault = str(reason)
        self.state.apply("system", {"type": "servo_stop"})
        print("[SERVO ROS FAULT]", reason)

    def ros_status(self):
        with self._ros_lock:
            return {
                "enabled": self._ros is not None,
                "connected": bool(self._ros and self._ros.connected),
                "fault": self._ros_fault,
                "topic": self._ros.topic if self._ros else None,
            }

    def _on_message(self, agent, message):
        """Handle a request and echo its correlation identifier."""
        agent_id = agent.agent_id
        request_type = message.get("type")
        request_id = message.get("request_id")

        try:
            if "servo_control" not in agent.roles:
                raise ValueError("Agent does not have servo_control role")
            if (not isinstance(request_id, str) or not request_id
                    or len(request_id) > 128):
                raise ValueError("Valid request_id is required")

            # Fail closed if the ROS output has become unavailable.
            if self._ros is not None and not self._ros_ready():
                self._fault_ros("rosbridge_disconnected")

            if self._ros_fault is not None and request_type != "servo_stop":
                raise ValueError("ROSBridge fault: " + self._ros_fault)

            state = self.state.apply(agent_id=agent_id, message=message)

            response = {
                "type": "servo_ack",
                "request": request_type,
                "request_id": request_id,
                "accepted": True,
                "state": state,
            }
        except (TypeError, ValueError) as error:
            response = {
                "type": "servo_ack",
                "request": request_type,
                "request_id": request_id,
                "accepted": False,
                "error": str(error),
                "state": self.state.snapshot(),
            }
        try:
            self.handler.send(agent_id, response)
        except ConnectionError:
            pass

    def _monitor(self):
        """Monitor command expiry, agent connectivity and ROS status."""
        previous_state = None
        while self._running.is_set():
            state = self.state.check_connections(
                self.handler.connected_agents
            )
            if self._ros is not None and not self._ros_ready():
                self._fault_ros("rosbridge_disconnected")
            if state != previous_state:
                print("[SERVO STATE]", state)
                previous_state = state
            time.sleep(0.02)

    def _publish_ros(self):
        """Publish latest authorized directions at a fixed rate.

        Never convert directions to speeds here. Zero is published on a
        transition to disarmed, provided ROSBridge is still connected.
        ROS 2 must enforce its own input watchdog independently.
        """
        previous_armed = False
        next_tick = time.monotonic()

        while self._running.is_set():
            state = self.state.snapshot()
            if not self._ros.connected:
                self._fault_ros("rosbridge_disconnected")
                break

            armed = bool(state["armed"])
            seq = state["last_seq"]
            with self._ros_lock:
                faulted = self._ros_fault is not None

            try:
                if faulted:
                    break
                if armed and seq >= 0:
                    self._ros.publish(state["linear"], state["angular"])
                    previous_armed = True
                elif previous_armed:
                    self._ros.zero()
                    previous_armed = False
                # A newly armed session without axes sends only zero.
                elif armed:
                    self._ros.zero()
            except Exception as exc:
                self._fault_ros("rosbridge_publish_failed: " + str(exc))
                break

            next_tick += self._ros_period
            delay = next_tick - time.monotonic()
            if delay < 0:
                next_tick = time.monotonic()
                delay = 0
            # Event.wait returns immediately when stopped if using inverse event;
            # ordinary sleep bounded by ROS publish period is sufficient here.
            time.sleep(delay)

        # No replay of previous commands following a ROSBridge reconnect.

    def start(self):
        if self._ros is not None:
            self._ros.connect()
        try:
            self.handler.start()
        except Exception:
            if self._ros is not None:
                self._ros.close()
            raise

        self._running.set()
        self._monitor_thread = threading.Thread(
            target=self._monitor, daemon=True
        )
        self._monitor_thread.start()
        if self._ros is not None:
            self._publisher_thread = threading.Thread(
                target=self._publish_ros, daemon=True
            )
            self._publisher_thread.start()
        print("[SERVO MASTER] Started", "ROSBridge" if self._ros else "offline")

    def stop(self):
        self._running.clear()
        self.state.apply("system", {"type": "servo_stop"})
        self.handler.stop()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
        if self._publisher_thread is not None:
            self._publisher_thread.join(timeout=2.0)
        if self._ros is not None:
            try:
                if self._ros.connected:
                    self._ros.zero()
            except Exception:
                pass
            self._ros.close()
        print("[SERVO MASTER] Stopped")


def main():
    parser = argparse.ArgumentParser(description="Servo master")
    parser.add_argument("--rosbridge", action="store_true",
                        help="Enable direction-only ROSBridge publication")
    parser.add_argument("--ros-host", default="127.0.0.1")
    parser.add_argument("--ros-port", type=int, default=9090)
    parser.add_argument("--ros-topic", default="/gh_servo/directions")
    parser.add_argument("--ros-rate", type=float, default=20.0)
    args = parser.parse_args()

    master = ServoMaster(
        rosbridge=args.rosbridge,
        ros_host=args.ros_host,
        ros_port=args.ros_port,
        ros_topic=args.ros_topic,
        ros_rate=args.ros_rate,
    )
    try:
        master.start()
        print("Press Ctrl+C to stop")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        master.stop()


if __name__ == "__main__":
    main()
