"""Interactive ROS-independent Servo teleoperation agent.

Uses the existing framework StreamClient.

Run:
    python -m projects.servo_teleop.agents.control_agent

The ServoMaster must already be running.

This application sends directional axis states only.
It does not connect to ROS or move a robot.
"""

from pathlib import Path
import sys
import threading
import time


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.core import Agent
from framework.communication.workflow import StreamClient


HOST = "127.0.0.1"
PORT = 9060
UPDATE_HZ = 20.0
ARM_ACK_TIMEOUT = 2.0

AXES = {
    "x": 0,
    "y": 1,
    "z": 2,
    "rx": 3,
    "ry": 4,
    "rz": 5,
}


class ServoControlAgent:
    def __init__(
        self,
        host=HOST,
        port=PORT,
        update_hz=UPDATE_HZ,
    ):
        if update_hz <= 0:
            raise ValueError("update_hz must be positive")

        self.update_hz = float(update_hz)
        self.period = 1.0 / self.update_hz

        self.lock = threading.RLock()

        self.axes = [0] * 6
        self.seq = 0
        self.armed = False

        self.stop_event = threading.Event()
        self.worker = None

        self.arm_event = threading.Event()
        self.awaiting_arm = False
        self.arm_response = None

        self.client = StreamClient(
            agent=Agent(
                agent_id="servo_control_pc",
                roles=["servo_control"],
            ),
            host=host,
            port=port,
            on_message=self._on_message,
            on_disconnect=self._on_disconnect,
        )

    def connect(self):
        self.client.connect()

        if not self.client.registered:
            raise ConnectionError(
                "Agent registration failed"
            )

        print("[CONNECTED] Servo control agent registered")

    def _disable_local(self, reason):
        """Immediately disable the local publishing loop."""
        with self.lock:
            self.armed = False
            self.axes = [0] * 6
            self.stop_event.set()

        print(f"\n[DISARMED] {reason}")

    def _on_disconnect(self):
        self._disable_local("TCP connection lost")
        self.arm_event.set()

    def _on_message(self, message):
        if message.get("type") != "servo_ack":
            print("[MASTER MESSAGE]", message)
            return

        with self.lock:
            awaiting_arm = self.awaiting_arm

            if awaiting_arm:
                self.arm_response = message
                self.arm_event.set()
                return

            active = self.armed

        # A rejected command means the current control
        # session must no longer be trusted.
        if not message.get("accepted", False) and active:
            self._disable_local(
                message.get("error", "Command rejected")
            )

    def arm(self):
        """Explicitly arm and start continuous publishing."""
        with self.lock:
            if self.armed:
                print("[INFO] Already armed")
                return

            if not self.client.registered:
                print("[ERROR] Agent is not connected")
                return

            # Arming always starts at zero velocity.
            self.axes = [0] * 6
            self.seq = 0
            self.arm_response = None
            self.arm_event.clear()
            self.awaiting_arm = True

        try:
            self.client.send({"type": "servo_arm"})

            acknowledged = self.arm_event.wait(
                ARM_ACK_TIMEOUT
            )

            with self.lock:
                response = self.arm_response
                self.awaiting_arm = False

            if (
                not acknowledged
                or response is None
                or not response.get("accepted", False)
                or not response.get("state", {}).get("armed", False)
            ):
                print("[ERROR] Arming was not acknowledged")

                if response is not None:
                    print(response)

                # If the arm acknowledgement was delayed,
                # the master may have armed regardless.
                self._send_stop_best_effort()
                return

            if not self.client.registered:
                print("[ERROR] Connection lost during arming")
                return

            with self.lock:
                self.armed = True
                self.stop_event.clear()

                self.worker = threading.Thread(
                    target=self._publish_loop,
                    name="servo-command-stream",
                    daemon=True,
                )

                self.worker.start()

            print("[ARMED] Streaming started at "
                  f"{self.update_hz:g} Hz")

        except Exception as exc:
            print(f"[ERROR] Arm failed: {exc}")
            self._send_stop_best_effort()

        finally:
            with self.lock:
                self.awaiting_arm = False

    def _publish_loop(self):
        """Send the latest directional state periodically."""
        next_publish = time.monotonic()

        while not self.stop_event.is_set():
            if not self.client.registered:
                self._disable_local(
                    "Connection not registered"
                )
                break

            with self.lock:
                if not self.armed:
                    break

                command = {
                    "type": "servo_axes",
                    "seq": self.seq,
                    "linear": list(self.axes[:3]),
                    "angular": list(self.axes[3:]),
                }

                self.seq += 1

            try:
                self.client.send(command)

            except Exception as exc:
                self._disable_local(
                    f"Command transmission failed: {exc}"
                )
                break

            next_publish += self.period

            remaining = next_publish - time.monotonic()

            # Never transmit a burst of old scheduled commands.
            if remaining < 0:
                next_publish = time.monotonic()
                remaining = 0

            if self.stop_event.wait(remaining):
                break

    def set_axis(self, axis_name, direction):
        """Set one axis without modifying the other axes."""
        with self.lock:
            if not self.armed:
                print("[ERROR] Arm the controller first")
                return

            index = AXES[axis_name]
            self.axes[index] = direction

            self._print_state()

    def zero(self):
        """Set every axis to zero while remaining armed."""
        with self.lock:
            self.axes = [0] * 6
            self._print_state()

    def _print_state(self):
        print(
            f"[AXES] linear={self.axes[:3]} "
            f"angular={self.axes[3:]} "
            f"armed={self.armed}"
        )

    def status(self):
        with self.lock:
            self._print_state()
            print(
                f"[STATUS] connected={self.client.connected} "
                f"registered={self.client.registered} "
                f"seq={self.seq}"
            )

    def _send_stop_best_effort(self):
        try:
            if self.client.registered:
                self.client.send({
                    "type": "servo_stop"
                })
        except Exception as exc:
            print(f"[WARNING] Stop delivery failed: {exc}")

    def stop(self):
        """Stop the publishing loop and disarm the master."""
        with self.lock:
            self.armed = False
            self.axes = [0] * 6
            self.stop_event.set()
            worker = self.worker

        if (
            worker is not None
            and worker is not threading.current_thread()
        ):
            worker.join(timeout=2.0)

            if worker.is_alive():
                print(
                    "[WARNING] Publisher thread did not "
                    "stop within timeout"
                )

        self._send_stop_best_effort()

        with self.lock:
            self.worker = None

        print("[STOP] Control disarmed locally; stop requested")

    def close(self):
        self.stop()
        self.client.close()


HELP = """
Commands
--------------------------------------------------
arm              Arm the control session
stop             Stop and disarm
zero             Set all six axes to zero
status           Show current state

x+  x-  x0       Linear X positive / negative / zero
y+  y-  y0       Linear Y positive / negative / zero
z+  z-  z0       Linear Z positive / negative / zero

rx+ rx- rx0      Angular X positive / negative / zero
ry+ ry- ry0      Angular Y positive / negative / zero
rz+ rz- rz0      Angular Z positive / negative / zero

help             Show commands
quit             Stop and exit

Each axis can be selected independently.
Commands are refreshed at 20 Hz while armed.
--------------------------------------------------
"""


def main():
    controller = ServoControlAgent()

    try:
        controller.connect()
        print(HELP)

        while True:
            try:
                command = input("servo> ").strip().lower()

            except EOFError:
                break

            if not command:
                continue

            if command == "help":
                print(HELP)

            elif command == "arm":
                controller.arm()

            elif command == "stop":
                controller.stop()

            elif command == "zero":
                controller.zero()

            elif command == "status":
                controller.status()

            elif command in {"quit", "exit"}:
                break

            elif (
                len(command) >= 2
                and command[:-1] in AXES
                and command[-1] in "+-0"
            ):
                direction = {
                    "+": 1,
                    "-": -1,
                    "0": 0,
                }[command[-1]]

                controller.set_axis(
                    command[:-1],
                    direction,
                )

            else:
                print(
                    "[ERROR] Unknown command. Type help."
                )

    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")

    except Exception as exc:
        print(f"[ERROR] {exc}")

    finally:
        controller.close()
        print("[EXIT] Control agent closed")


if __name__ == "__main__":
    main()