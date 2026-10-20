"""Agent-side persistent streaming workflow client."""

import threading
from typing import Any, Callable, Dict

from framework.communication.core import Agent
from framework.communication.transport import TCPStreamClient


class StreamClient:
    """
    Agent-aware bidirectional streaming client.

    Registration must be acknowledged before application
    messages can be sent.
    """

    def __init__(
        self,
        agent: Agent,
        host: str,
        port: int,
        on_message: Callable[[Dict[str, Any]], None],
        on_disconnect: Callable[[], None] | None = None,
        registration_timeout: float = 5.0,
    ):
        if not isinstance(agent, Agent):
            raise TypeError("agent must be an Agent.")

        if not callable(on_message):
            raise TypeError("on_message must be callable.")

        if registration_timeout <= 0:
            raise ValueError(
                "registration_timeout must be positive."
            )

        self.agent = agent
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.registration_timeout = float(
            registration_timeout
        )

        self._registration_event = threading.Event()
        self._lock = threading.RLock()
        self._registered = False
        self._registration_error = None

        self.tcp_client = TCPStreamClient(
            host=host,
            port=port,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
        )

    @property
    def connected(self) -> bool:
        return self.tcp_client.connected

    @property
    def registered(self) -> bool:
        with self._lock:
            return (
                self._registered
                and self.tcp_client.connected
            )

    def connect(self) -> None:
        """Connect and wait for registration acknowledgement."""

        with self._lock:
            if self.tcp_client.connected:
                raise RuntimeError(
                    "Stream client is already connected."
                )

            self._registered = False
            self._registration_error = None
            self._registration_event.clear()

        self.tcp_client.connect()

        try:
            self.tcp_client.send({
                "type": "agent_register",
                "agent": self.agent.to_dict(),
            })

            acknowledged = self._registration_event.wait(
                self.registration_timeout
            )

            if not acknowledged:
                raise TimeoutError(
                    "Agent registration acknowledgement timed out."
                )

            with self._lock:
                error = self._registration_error
                registered = self._registered

            if error is not None:
                raise ConnectionError(error)

            if not registered:
                raise ConnectionError(
                    "Agent registration was not completed."
                )

        except Exception:
            self.tcp_client.close()
            raise

    def send(self, message: Dict[str, Any]) -> None:
        """Send an application message after registration."""

        if not isinstance(message, dict):
            raise TypeError("message must be a dictionary.")

        if message.get("type") in {
            "agent_register",
            "agent_registered",
            "agent_rejected",
        }:
            raise ValueError(
                "Message type is reserved for stream registration."
            )

        if not self.registered:
            raise ConnectionError(
                "Agent stream is not registered."
            )

        self.tcp_client.send(message)

    def close(self) -> None:
        with self._lock:
            self._registered = False
            self._registration_event.set()

        self.tcp_client.close()

    def _handle_message(self, message: Dict[str, Any]) -> None:
        message_type = message.get("type")

        if message_type == "agent_registered":
            with self._lock:
                if message.get("agent_id") != self.agent.agent_id:
                    self._registration_error = (
                        "Registration acknowledgement Agent ID mismatch."
                    )
                else:
                    self._registered = True

                self._registration_event.set()
            return

        if message_type == "agent_rejected":
            with self._lock:
                self._registration_error = message.get(
                    "reason",
                    "Agent registration rejected.",
                )
                self._registered = False
                self._registration_event.set()
            return

        if not self.registered:
            return

        self.on_message(message)

    def _handle_disconnect(self) -> None:
        with self._lock:
            self._registered = False
            self._registration_event.set()

        if self.on_disconnect is not None:
            self.on_disconnect()
