"""Grasshopper-facing TCP interface for Servo teleoperation.

Uses the framework's existing TCPStreamServer.
No ROS dependency.
"""

from framework.communication.transport.tcp import (
    TCPStreamServer,
)

from projects.servo_teleop.operations.input_state import (
    GrasshopperInputState,
)


class GrasshopperTCPInterface:
    def __init__(
        self,
        host="127.0.0.1",
        port=9061,
        input_timeout=0.5,
    ):
        self.state = GrasshopperInputState(
            input_timeout=input_timeout
        )

        self.server = TCPStreamServer(
            host=host,
            port=port,
            on_message=self._on_message,
            on_disconnect=self._on_disconnect,
        )

    @property
    def running(self):
        return self.server.running

    @property
    def client_ids(self):
        return self.server.client_ids

    def _on_message(self, client_id, message):
        try:
            state = self.state.apply(client_id, message)

            reply = {
                "type": "gh_ack",
                "request": message.get("type"),
                "accepted": True,
                "state": state,
            }

        except (ValueError, TypeError) as exc:
            reply = {
                "type": "gh_ack",
                "request": (
                    message.get("type")
                    if isinstance(message, dict)
                    else None
                ),
                "accepted": False,
                "error": str(exc),
                "state": self.state.snapshot(),
            }

        try:
            self.server.send(client_id, reply)
        except (ConnectionError, OSError):
            # Connection may have closed before acknowledgement.
            pass

    def _on_disconnect(self, client_id):
        self.state.disconnected(client_id)

    def snapshot(self):
        return self.state.snapshot()

    def start(self):
        self.server.start()

    def stop(self):
        # Stop closes the active sockets. Their disconnect
        # callbacks disarm the owning client.
        self.server.stop()

        # Also ensure the interface cannot retain an armed
        # state if shutdown occurs without an owner callback.
        state = self.state.snapshot()
        if state["armed"]:
            self.state.disconnected(state["owner"])


if __name__ == "__main__":
    import time

    interface = GrasshopperTCPInterface()

    try:
        interface.start()
        print("[GH INTERFACE] Started on localhost:9061")

        while True:
            time.sleep(0.1)
            interface.snapshot()

    except KeyboardInterrupt:
        pass

    finally:
        interface.stop()
        print("[GH INTERFACE] Stopped")