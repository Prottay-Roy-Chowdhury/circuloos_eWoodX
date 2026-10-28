"""Thread-safe, ROS-independent Grasshopper input state."""

import threading
import time
import uuid


ZERO = (0, 0, 0)


class GrasshopperInputState:
    def __init__(self, input_timeout=0.5):
        if input_timeout <= 0:
            raise ValueError("input_timeout must be positive")

        self.input_timeout = float(input_timeout)
        self._lock = threading.RLock()

        self._armed = False
        self._owner = None
        self._session = None
        self._linear = ZERO
        self._angular = ZERO
        self._seq = -1
        self._updated_at = None
        self._reason = "initial"

    @staticmethod
    def _axes(values, name):
        if (
            not isinstance(values, (list, tuple))
            or len(values) != 3
            or any(
                type(v) is not int or v not in (-1, 0, 1)
                for v in values
            )
        ):
            raise ValueError(
                f"{name} must contain 3 integers in (-1, 0, 1)"
            )
        return tuple(values)

    def _disarm(self, reason):
        self._armed = False
        self._owner = None
        self._session = None
        self._linear = ZERO
        self._angular = ZERO
        self._seq = -1
        self._updated_at = None
        self._reason = reason

    def _expire(self):
        if (
            self._armed
            and self._updated_at is not None
            and time.monotonic() - self._updated_at
            > self.input_timeout
        ):
            self._disarm("input_timeout")

    def snapshot(self):
        with self._lock:
            self._expire()
            return {
                "armed": self._armed,
                "owner": self._owner,
                "session": self._session,
                "linear": list(self._linear),
                "angular": list(self._angular),
                "last_seq": self._seq,
                "reason": self._reason,
            }

    def apply(self, client_id, message):
        if not isinstance(message, dict):
            raise ValueError("message must be a dictionary")

        if not isinstance(client_id, str) or not client_id:
            raise ValueError("Invalid client ID")

        command = message.get("type")

        with self._lock:
            self._expire()

            if command == "gh_status":
                return self.snapshot()

            if command == "gh_arm":
                if self._armed:
                    raise ValueError("Input already armed")

                # Every arm creates a new control session.
                self._armed = True
                self._owner = client_id
                self._session = uuid.uuid4().hex
                self._linear = ZERO
                self._angular = ZERO
                self._seq = -1
                self._updated_at = time.monotonic()
                self._reason = "armed"
                return self.snapshot()

            if command == "gh_stop":
                # Allow any connected local client to request
                # disarming, without granting it motion control.
                self._disarm("explicit_stop")
                return self.snapshot()

            if command == "gh_axes":
                if not self._armed:
                    raise ValueError("Input is not armed")

                if self._owner != client_id:
                    raise ValueError("Not the input owner")

                if message.get("session") != self._session:
                    raise ValueError("Invalid control session")

                seq = message.get("seq")
                if type(seq) is not int or seq < 0:
                    raise ValueError("Invalid sequence number")

                if seq <= self._seq:
                    raise ValueError("Stale or duplicate sequence")

                linear = self._axes(
                    message.get("linear"), "linear"
                )
                angular = self._axes(
                    message.get("angular"), "angular"
                )

                self._linear = linear
                self._angular = angular
                self._seq = seq
                self._updated_at = time.monotonic()
                self._reason = "input_received"
                return self.snapshot()

            raise ValueError(f"Unknown command: {command}")

    def disconnected(self, client_id):
        with self._lock:
            if self._owner == client_id:
                self._disarm("owner_disconnected")

            return self.snapshot()