"""Grasshopper-facing TCP interface for Servo teleoperation."""

from framework.communication.transport.tcp import TCPStreamServer

from projects.servo_teleop.operations.input_state import (
    GrasshopperInputState,
)


class GrasshopperTCPInterface:
    def __init__(
        self,
        host="127.0.0.1",
        port=9061,
        input_timeout=0.5,
        status_provider=None,
    ):
        self.state = GrasshopperInputState(input_timeout)
        self.status_provider = status_provider

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

    def _control_status(self):
        if self.status_provider is None:
            return {
                "state": "STANDALONE",
                "reason": "no coordinator attached",
            }

        return self.status_provider()

    def _on_message(self, client_id, message):
        request = (
            message.get("type")
            if isinstance(message, dict)
            else None
        )

        try:
            control = self._control_status()

            if request in ("gh_arm", "gh_axes"):
                if control["state"] in ("FAULT", "STOPPED"):
                    raise ValueError(
                        "Control unavailable: "
                        + control["state"]
                        + " - "
                        + control.get("reason", "")
                    )

            if request == "gh_arm":
                if control["state"] not in (
                    "READY", "STANDALONE"
                ):
                    raise ValueError(
                        "Cannot arm in state: "
                        + control["state"]
                    )

            state = self.state.apply(client_id, message)

            reply = {
                "type": "gh_ack",
                "request": request,
                "accepted": True,
                "state": state,
            }

        except (ValueError, TypeError) as exc:
            reply = {
                "type": "gh_ack",
                "request": request,
                "accepted": False,
                "error": str(exc),
                "state": self.state.snapshot(),
            }

        # Always include coordinator status, even for rejections.
        reply["control"] = self._control_status()

        try:
            self.server.send(client_id, reply)
        except (ConnectionError, OSError):
            pass

    def _on_disconnect(self, client_id):
        self.state.disconnected(client_id)

    def snapshot(self):
        return self.state.snapshot()

    def start(self):
        self.server.start()

    def stop(self):
        self.server.stop()

        state = self.state.snapshot()
        if state["armed"]:
            self.state.disconnected(state["owner"])


if __name__ == "__main__":
    import time

    interface = GrasshopperTCPInterface()

    try:
        interface.start()

        while True:
            time.sleep(0.1)
            interface.snapshot()

    except KeyboardInterrupt:
        pass

    finally:
        interface.stop()