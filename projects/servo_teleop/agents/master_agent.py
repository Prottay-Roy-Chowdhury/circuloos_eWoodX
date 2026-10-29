"""Servo teleoperation master.

Operating modes:
    1. Offline: TCP master without ROSBridge
    2. ROSBridge: TCP master with direction-only ROS publishing

Running without command-line arguments opens an
interactive configuration menu.

ROSBridge publishes:
    Topic: /gh_servo/directions
    Type:  std_msgs/Int8MultiArray
    Data:  [X, Y, Z, RX, RY, RZ]

All directions must be -1, 0 or +1.

The ROS 2 node is responsible for velocity scaling,
frame_id, timestamps and final TwistStamped publishing.
"""

import argparse
from pathlib import Path
import sys
import threading
import time

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.workflow import StreamHandler

from projects.servo_teleop.operations.control_state import (
    ServoControlState,
)

from projects.servo_teleop.operations.ros_direction_publisher import (
    ROSDirectionPublisher,
)


# ==========================================================
# DEFAULT CONFIGURATION
# ==========================================================

DEFAULT_MASTER_HOST = "127.0.0.1"
DEFAULT_MASTER_PORT = 9060

DEFAULT_COMMAND_TIMEOUT = 0.3

DEFAULT_ROS_HOST = "127.0.0.1"
DEFAULT_ROS_PORT = 9090
DEFAULT_ROS_TOPIC = "/gh_servo/directions"
DEFAULT_ROS_RATE = 20.0


# ==========================================================
# SERVO MASTER
# ==========================================================

class ServoMaster:

    def __init__(
        self,
        host=DEFAULT_MASTER_HOST,
        port=DEFAULT_MASTER_PORT,
        command_timeout=DEFAULT_COMMAND_TIMEOUT,
        rosbridge=False,
        ros_host=DEFAULT_ROS_HOST,
        ros_port=DEFAULT_ROS_PORT,
        ros_topic=DEFAULT_ROS_TOPIC,
        ros_rate=DEFAULT_ROS_RATE,
        ros_client=None,
    ):

        if ros_rate <= 0:
            raise ValueError("ros_rate must be positive")

        # --------------------------------------------------
        # Existing servo control state
        # --------------------------------------------------

        self.state = ServoControlState(
            command_timeout=command_timeout
        )

        # --------------------------------------------------
        # Master TCP server
        # --------------------------------------------------

        self.handler = StreamHandler(
            host=host,
            port=port,
            on_message=self._on_message,
        )

        self._running = threading.Event()

        self._monitor_thread = None
        self._publisher_thread = None

        # --------------------------------------------------
        # ROSBridge configuration
        # --------------------------------------------------

        self._ros_period = 1.0 / float(ros_rate)

        self._ros_fault = None
        self._ros_lock = threading.RLock()

        self._ros = None

        if rosbridge:
            self._ros = ROSDirectionPublisher(
                host=ros_host,
                port=ros_port,
                topic=ros_topic,
                client=ros_client,
            )

    # ======================================================
    # ROS STATUS
    # ======================================================

    def _ros_ready(self):

        with self._ros_lock:
            return (
                self._ros_fault is None
                and (
                    self._ros is None
                    or self._ros.connected
                )
            )

    def _fault_ros(self, reason):

        with self._ros_lock:

            if self._ros_fault is not None:
                return

            self._ros_fault = str(reason)

        # Revoke existing master authorization.
        self.state.apply(
            "system",
            {"type": "servo_stop"},
        )

        print("[SERVO ROS FAULT]", reason)

    def ros_status(self):

        with self._ros_lock:

            return {
                "enabled": self._ros is not None,
                "connected": bool(
                    self._ros and self._ros.connected
                ),
                "fault": self._ros_fault,
                "topic": (
                    self._ros.topic
                    if self._ros else None
                ),
            }

    # ======================================================
    # MASTER TCP MESSAGE HANDLER
    # ======================================================

    def _on_message(self, agent, message):

        agent_id = agent.agent_id

        request_type = message.get("type")
        request_id = message.get("request_id")

        try:

            if "servo_control" not in agent.roles:
                raise ValueError(
                    "Agent does not have servo_control role"
                )

            if (
                not isinstance(request_id, str)
                or not request_id
                or len(request_id) > 128
            ):
                raise ValueError(
                    "Valid request_id is required"
                )

            # Reject new commands when ROSBridge
            # becomes unavailable.

            if (
                self._ros is not None
                and not self._ros_ready()
            ):
                self._fault_ros(
                    "rosbridge_disconnected"
                )

            if (
                self._ros_fault is not None
                and request_type != "servo_stop"
            ):
                raise ValueError(
                    "ROSBridge fault: " + self._ros_fault
                )

            # Existing state validation.
            state = self.state.apply(
                agent_id=agent_id,
                message=message,
            )

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
            self.handler.send(
                agent_id,
                response,
            )

        except ConnectionError:
            pass

    # ======================================================
    # MASTER WATCHDOG
    # ======================================================

    def _monitor(self):

        previous_state = None

        while self._running.is_set():

            state = self.state.check_connections(
                self.handler.connected_agents
            )

            if (
                self._ros is not None
                and not self._ros_ready()
            ):
                self._fault_ros(
                    "rosbridge_disconnected"
                )

            if state != previous_state:

                print(
                    "[SERVO STATE]",
                    state,
                )

                previous_state = state

            time.sleep(0.02)

    # ======================================================
    # ROS DIRECTION PUBLISHING
    # ======================================================

    def _publish_ros(self):

        previous_armed = False
        next_tick = time.monotonic()

        while self._running.is_set():

            state = self.state.snapshot()

            if not self._ros.connected:

                self._fault_ros(
                    "rosbridge_disconnected"
                )

                break

            armed = bool(state["armed"])
            seq = state["last_seq"]

            with self._ros_lock:
                faulted = self._ros_fault is not None

            try:

                if faulted:
                    break

                # ------------------------------------------
                # Valid active command
                # ------------------------------------------

                if armed and seq >= 0:

                    self._ros.publish(
                        state["linear"],
                        state["angular"],
                    )

                    previous_armed = True

                # ------------------------------------------
                # Session transitioned to disarmed
                # ------------------------------------------

                elif previous_armed:

                    self._ros.zero()

                    previous_armed = False

                # ------------------------------------------
                # Session armed, no axis command received
                # ------------------------------------------

                elif armed:

                    self._ros.zero()

            except Exception as exc:

                self._fault_ros(
                    "rosbridge_publish_failed: "
                    + str(exc)
                )

                break

            # ----------------------------------------------
            # Fixed-rate publishing
            # ----------------------------------------------

            next_tick += self._ros_period

            delay = next_tick - time.monotonic()

            if delay < 0:

                next_tick = time.monotonic()
                delay = 0

            time.sleep(delay)

    # ======================================================
    # START
    # ======================================================

    def start(self):

        # Connect ROSBridge before allowing TCP
        # clients to initiate motion sessions.

        if self._ros is not None:

            print(
                "[SERVO MASTER] Connecting ROSBridge..."
            )

            self._ros.connect()

            print(
                "[SERVO MASTER] ROSBridge connected"
            )

            print(
                "[SERVO MASTER] Direction topic:",
                self._ros.topic,
            )

        try:
            self.handler.start()

        except Exception:

            if self._ros is not None:
                self._ros.close()

            raise

        self._running.set()

        # Master watchdog.
        self._monitor_thread = threading.Thread(
            target=self._monitor,
            daemon=True,
        )

        self._monitor_thread.start()

        # ROS publisher only exists in ROSBridge mode.
        if self._ros is not None:

            self._publisher_thread = threading.Thread(
                target=self._publish_ros,
                daemon=True,
            )

            self._publisher_thread.start()

        mode = (
            "ROSBridge"
            if self._ros is not None
            else "offline"
        )

        print(
            "[SERVO MASTER] Started",
            mode,
        )

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        self._running.clear()

        self.state.apply(
            "system",
            {"type": "servo_stop"},
        )

        self.handler.stop()

        if self._monitor_thread is not None:

            self._monitor_thread.join(
                timeout=2.0
            )

        if self._publisher_thread is not None:

            self._publisher_thread.join(
                timeout=2.0
            )

        if self._ros is not None:

            try:
                if self._ros.connected:
                    self._ros.zero()
            except Exception:
                pass

            self._ros.close()

        print("[SERVO MASTER] Stopped")


# ==========================================================
# INTERACTIVE CLI
# ==========================================================

def prompt_string(label, default):

    value = input(
        f"{label} [{default}]: "
    ).strip()

    return value if value else default


def prompt_port(label, default):

    while True:

        value = prompt_string(
            label,
            str(default),
        )

        try:

            port = int(value)

            if 1 <= port <= 65535:
                return port

        except ValueError:
            pass

        print(
            "Invalid port. Enter an integer "
            "between 1 and 65535."
        )


def prompt_positive_float(label, default):

    while True:

        value = prompt_string(
            label,
            str(default),
        )

        try:

            result = float(value)

            if (
                result > 0
                and result != float("inf")
                and result == result
            ):
                return result

        except ValueError:
            pass

        print(
            "Invalid value. Enter a finite "
            "positive number."
        )


def interactive_configuration(args):

    print()
    print("=" * 48)
    print("           SERVO TELEOP MASTER")
    print("=" * 48)

    print()
    print("Select operating mode:")
    print()
    print("  [1] Offline")
    print("  [2] ROSBridge")
    print()

    while True:

        choice = input(
            "Mode [1]: "
        ).strip()

        if choice == "" or choice == "1":
            args.mode = "offline"
            break

        if choice == "2":
            args.mode = "rosbridge"
            break

        print(
            "Invalid choice. Select 1 or 2."
        )

    if args.mode == "rosbridge":

        print()
        print("ROSBridge configuration")
        print("-" * 48)

        args.ros_host = prompt_string(
            "Host/IP",
            args.ros_host,
        )

        args.ros_port = prompt_port(
            "Port",
            args.ros_port,
        )

        while True:

            args.ros_topic = prompt_string(
                "Topic",
                args.ros_topic,
            )

            if args.ros_topic.startswith("/"):
                break

            print(
                "ROS topic must begin with '/'."
            )

        args.ros_rate = prompt_positive_float(
            "Publish rate Hz",
            args.ros_rate,
        )

    return args


def display_configuration(args):

    print()
    print("=" * 48)
    print("MASTER CONFIGURATION")
    print("=" * 48)

    print(
        "Mode:          ",
        args.mode,
    )

    print(
        "Master TCP:    ",
        f"{DEFAULT_MASTER_HOST}:{DEFAULT_MASTER_PORT}",
    )

    print(
        "Command timeout:",
        f"{DEFAULT_COMMAND_TIMEOUT} s",
    )

    if args.mode == "rosbridge":

        print(
            "ROSBridge:     ",
            f"{args.ros_host}:{args.ros_port}",
        )

        print(
            "ROS topic:     ",
            args.ros_topic,
        )

        print(
            "ROS rate:      ",
            f"{args.ros_rate:g} Hz",
        )

        print(
            "ROS msg type:   std_msgs/Int8MultiArray"
        )

    print("=" * 48)
    print()


# ==========================================================
# MAIN
# ==========================================================

def main():

    parser = argparse.ArgumentParser(
        description="Servo Teleoperation Master"
    )

    # Optional non-interactive mode selection.
    parser.add_argument(
        "--mode",
        choices=["offline", "rosbridge"],
        default=None,
        help=(
            "Select mode directly. "
            "Omit to open the interactive menu."
        ),
    )

    # Backward compatibility with earlier command.
    parser.add_argument(
        "--rosbridge",
        action="store_true",
        help="Shortcut for --mode rosbridge",
    )

    parser.add_argument(
        "--ros-host",
        default=DEFAULT_ROS_HOST,
    )

    parser.add_argument(
        "--ros-port",
        type=int,
        default=DEFAULT_ROS_PORT,
    )

    parser.add_argument(
        "--ros-topic",
        default=DEFAULT_ROS_TOPIC,
    )

    parser.add_argument(
        "--ros-rate",
        type=float,
        default=DEFAULT_ROS_RATE,
    )

    args = parser.parse_args()

    # ----------------------------------------------
    # Resolve mode
    # ----------------------------------------------

    if args.rosbridge:

        if args.mode == "offline":
            parser.error(
                "--rosbridge conflicts with "
                "--mode offline"
            )

        args.mode = "rosbridge"

    # Interactive menu when no mode is selected.
    if args.mode is None:

        try:
            args = interactive_configuration(args)

        except (KeyboardInterrupt, EOFError):
            print("\nStartup cancelled.")
            return

    # ----------------------------------------------
    # Validate selected ROS configuration
    # ----------------------------------------------

    if args.mode == "rosbridge":

        import math

        if not args.ros_host.strip():
            parser.error(
                "ROSBridge host cannot be empty"
            )

        if not 1 <= args.ros_port <= 65535:
            parser.error(
                "ROSBridge port must be 1-65535"
            )

        if not args.ros_topic.startswith("/"):
            parser.error(
                "ROS topic must begin with '/'"
            )

        if (
            not math.isfinite(args.ros_rate)
            or args.ros_rate <= 0
        ):
            parser.error(
                "ROS rate must be finite and positive"
            )

    # ----------------------------------------------
    # Display chosen configuration
    # ----------------------------------------------

    display_configuration(args)

    # ----------------------------------------------
    # Initialize master
    # ----------------------------------------------

    master = ServoMaster(
        host=DEFAULT_MASTER_HOST,
        port=DEFAULT_MASTER_PORT,
        command_timeout=DEFAULT_COMMAND_TIMEOUT,

        rosbridge=(
            args.mode == "rosbridge"
        ),

        ros_host=args.ros_host,
        ros_port=args.ros_port,
        ros_topic=args.ros_topic,
        ros_rate=args.ros_rate,
    )

    started = False

    try:

        master.start()
        started = True

        print("Press Ctrl+C to stop")

        while True:
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nShutdown requested.")

    except Exception as exc:
        print(
            "[SERVO MASTER ERROR]",
            exc,
        )

    finally:
        if started:
            master.stop()


if __name__ == "__main__":
    main()