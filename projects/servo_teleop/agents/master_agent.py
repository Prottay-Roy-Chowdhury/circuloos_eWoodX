"""Offline Servo teleoperation master.

Uses the existing framework StreamHandler.
Does not depend on ROS or Grasshopper.
"""

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


class ServoMaster:
    def __init__(
        self,
        host="127.0.0.1",
        port=9060,
        command_timeout=0.3,
    ):
        self.state = ServoControlState(
            command_timeout=command_timeout
        )

        self.handler = StreamHandler(
            host=host,
            port=port,
            on_message=self._on_message,
        )

        self._running = threading.Event()
        self._monitor_thread = None

    def _on_message(self, agent, message):
        """Handle messages from registered agents."""
        agent_id = agent.agent_id

        try:
            if "servo_control" not in agent.roles:
                raise ValueError(
                    "Agent does not have servo_control role"
                )

            state = self.state.apply(
                agent_id=agent_id,
                message=message,
            )

            response = {
                "type": "servo_ack",
                "accepted": True,
                "state": state,
            }

        except (TypeError, ValueError) as error:
            response = {
                "type": "servo_ack",
                "accepted": False,
                "error": str(error),
                "state": self.state.snapshot(),
            }

        try:
            self.handler.send(agent_id, response)
        except ConnectionError:
            # Agent may have disconnected after sending.
            pass

    def _monitor(self):
        """Monitor command expiry and agent connectivity."""
        previous_state = None

        while self._running.is_set():
            state = self.state.check_connections(
                self.handler.connected_agents
            )

            if state != previous_state:
                print("[SERVO STATE]", state)
                previous_state = state

            time.sleep(0.02)

    def start(self):
        self.handler.start()
        self._running.set()

        self._monitor_thread = threading.Thread(
            target=self._monitor,
            daemon=True,
        )
        self._monitor_thread.start()

        print("[SERVO MASTER] Started")

    def stop(self):
        self._running.clear()
        self.state.apply(
            "system",
            {"type": "servo_stop"},
        )

        self.handler.stop()

        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)

        print("[SERVO MASTER] Stopped")


def main():
    master = ServoMaster()

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