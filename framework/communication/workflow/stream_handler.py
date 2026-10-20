
"""Agent-aware streaming workflow handler."""

import threading
from typing import Any, Callable, Dict

from framework.communication.core import Agent
from framework.communication.transport import TCPStreamServer


class StreamHandler:
    """
    Master-side Agent registration and message dispatch.

    Registration is required before application messages.
    """

    def __init__(
        self,
        host: str,
        port: int,
        on_message: Callable[[Agent, Dict[str, Any]], None],
    ):
        if not callable(on_message):
            raise TypeError("on_message must be callable.")

        self.on_message = on_message

        self._lock = threading.Lock()

        self._agents: Dict[str, Agent] = {}
        self._connections: Dict[str, str] = {}
        self._client_agents: Dict[str, str] = {}

        self.tcp_server = TCPStreamServer(
            host=host,
            port=port,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
        )

    @property
    def connected_agents(self) -> list[str]:
        with self._lock:
            return list(self._agents.keys())

    def start(self) -> None:
        self.tcp_server.start()

    def stop(self) -> None:
        self.tcp_server.stop()

    def send(
        self,
        agent_id: str,
        message: Dict[str, Any],
    ) -> None:
        with self._lock:
            client_id = self._connections.get(agent_id)

        if client_id is None:
            raise ConnectionError(
                f"Agent is not registered: {agent_id}"
            )

        self.tcp_server.send(client_id, message)

    def _handle_message(
        self,
        client_id: str,
        message: Dict[str, Any],
    ) -> None:
        message_type = message.get("type")

        if message_type == "agent_register":
            self._register_agent(client_id, message)
            return

        with self._lock:
            agent_id = self._client_agents.get(client_id)
            agent = (
                self._agents.get(agent_id)
                if agent_id is not None
                else None
            )

        if agent is None:
            self._reject(
                client_id,
                "Connection has not registered an Agent.",
            )
            return

        if message_type in {
            "agent_registered",
            "agent_rejected",
        }:
            self._reject(
                client_id,
                "Reserved registration message type.",
            )
            return

        self.on_message(agent, message)

    def _register_agent(
        self,
        client_id: str,
        message: Dict[str, Any],
    ) -> None:
        try:
            agent = Agent.from_dict(message["agent"])

        except (KeyError, TypeError, ValueError) as error:
            self._reject(
                client_id,
                f"Invalid Agent registration: {error}",
            )
            return

        with self._lock:
            existing_id = self._connections.get(agent.agent_id)

            if existing_id is not None:
                reason = (
                    f"Agent already connected: {agent.agent_id}"
                )

            elif client_id in self._client_agents:
                reason = (
                    "Connection has already registered an Agent."
                )

            else:
                reason = None

                self._agents[agent.agent_id] = agent
                self._connections[agent.agent_id] = client_id
                self._client_agents[client_id] = agent.agent_id

        if reason is not None:
            self._reject(client_id, reason)
            return

        self.tcp_server.send(
            client_id,
            {
                "type": "agent_registered",
                "agent_id": agent.agent_id,
            },
        )

    def _reject(
        self,
        client_id: str,
        reason: str,
    ) -> None:
        """
        Report a protocol rejection without raising an
        exception from the transport callback.
        """

        try:
            self.tcp_server.send(
                client_id,
                {
                    "type": "agent_rejected",
                    "reason": reason,
                },
            )
        except (ConnectionError, OSError):
            pass
    
    def _handle_disconnect(self, client_id: str) -> None:
        with self._lock:
            agent_id = self._client_agents.pop(
                client_id,
                None,
            )

            if agent_id is not None:
                self._connections.pop(agent_id, None)
                self._agents.pop(agent_id, None)
