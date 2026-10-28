"""ROS-independent Servo master control state.

Session-scoped commands, sequence validation, owner checks,
timeouts, and explicit disarming.
"""

import threading
import time
import uuid


ZERO_AXES = (0, 0, 0)


class ServoControlState:
    def __init__(self, command_timeout=0.3):
        if command_timeout <= 0:
            raise ValueError("command_timeout must be positive")

        self.command_timeout = float(command_timeout)
        self._lock = threading.RLock()

        self._armed = False
        self._owner = None
        self._session = None
        self._linear = ZERO_AXES
        self._angular = ZERO_AXES
        self._last_seq = -1
        self._last_update = None
        self._reason = "initial"

    @staticmethod
    def _validate_axes(value, name):
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 3
            or any(
                type(axis) is not int or axis not in (-1, 0, 1)
                for axis in value
            )
        ):
            raise ValueError(
                f"{name} must contain three integers: -1, 0, or 1"
            )
        return tuple(value)

    def _disarm(self, reason):
        self._armed = False
        self._owner = None
        self._session = None
        self._linear = ZERO_AXES
        self._angular = ZERO_AXES
        self._last_seq = -1
        self._last_update = None
        self._reason = reason

    def _expire_if_needed(self):
        if (
            self._armed
            and self._last_update is not None
            and time.monotonic() - self._last_update
            > self.command_timeout
        ):
            self._disarm("command_timeout")

    def apply(self, agent_id, message):
        if not isinstance(message, dict):
            raise ValueError("message must be a dictionary")

        command_type = message.get("type")

        with self._lock:
            self._expire_if_needed()

            if command_type == "servo_stop":
                # Preserve the existing global-stop behavior.
                # This is an emergency disarm request, not
                # authorization to command movement.
                self._disarm("explicit_stop")
                return self.snapshot()

            if command_type == "servo_arm":
                if self._armed:
                    raise ValueError(
                        f"Control already owned by {self._owner}"
                    )

                self._armed = True
                self._owner = agent_id
                self._session = uuid.uuid4().hex
                self._linear = ZERO_AXES
                self._angular = ZERO_AXES
                self._last_seq = -1
                self._last_update = time.monotonic()
                self._reason = "armed"
                return self.snapshot()

            if command_type == "servo_axes":
                if not self._armed:
                    raise ValueError("Control is not armed")

                if agent_id != self._owner:
                    raise ValueError(
                        "Agent does not own control session"
                    )

                if message.get("session") != self._session:
                    raise ValueError(
                        "Invalid or expired master session"
                    )

                seq = message.get("seq")
                if type(seq) is not int or seq < 0:
                    raise ValueError(
                        "seq must be a non-negative integer"
                    )

                if seq <= self._last_seq:
                    raise ValueError(
                        "Out-of-order or duplicate sequence"
                    )

                linear = self._validate_axes(
                    message.get("linear"), "linear"
                )
                angular = self._validate_axes(
                    message.get("angular"), "angular"
                )

                self._linear = linear
                self._angular = angular
                self._last_seq = seq
                self._last_update = time.monotonic()
                self._reason = "command_received"
                return self.snapshot()

            raise ValueError(
                f"Unknown control message: {command_type}"
            )

    def check_connections(self, connected_agent_ids):
        with self._lock:
            self._expire_if_needed()

            if (
                self._armed
                and self._owner not in connected_agent_ids
            ):
                self._disarm("owner_disconnected")

            return self.snapshot()

    def snapshot(self):
        with self._lock:
            self._expire_if_needed()
            return {
                "armed": self._armed,
                "owner": self._owner,
                "session": self._session,
                "linear": list(self._linear),
                "angular": list(self._angular),
                "last_seq": self._last_seq,
                "reason": self._reason,
            }