"""Agent-side client for distributed workflow coordination."""

from framework.communication.core import (
    Action,
    Agent,
)

from framework.communication.storage import (
    AgentActionStore,
)

from framework.communication.transport import (
    TCPClient,
)


class WorkflowClient:
    """
    Agent-side workflow coordination client.

    Requests work from a remote workflow handler and
    persists claimed actions in the agent-local store.
    """

    def __init__(
        self,
        tcp_client: TCPClient,
        agent: Agent,
        local_store: AgentActionStore,
    ):
        if not isinstance(
            tcp_client,
            TCPClient,
        ):
            raise TypeError(
                "tcp_client must be a TCPClient."
            )

        if not isinstance(
            agent,
            Agent,
        ):
            raise TypeError(
                "agent must be an Agent."
            )

        if not isinstance(
            local_store,
            AgentActionStore,
        ):
            raise TypeError(
                "local_store must be an AgentActionStore."
            )

        if (
            local_store.agent.agent_id
            != agent.agent_id
        ):
            raise ValueError(
                "local_store must belong to the same agent."
            )

        self.tcp_client = tcp_client
        self.agent = agent
        self.local_store = local_store

    def claim_next(
        self,
    ) -> Action | None:
        """
        Request the next eligible action from the master.

        If an action is returned, reconstruct it and
        persist it in the local agent store.
        """

        response = self.tcp_client.send(
            {
                "command": "claim_next",
                "agent": self.agent.to_dict(),
            }
        )

        if (
            response.get("status")
            != "ok"
        ):
            raise RuntimeError(
                response.get(
                    "message",
                    "Workflow request failed.",
                )
            )

        action_data = response.get(
            "action"
        )

        if action_data is None:
            return None

        if not isinstance(
            action_data,
            dict,
        ):
            raise TypeError(
                "Received action must be a dictionary."
            )

        action = Action.from_dict(
            action_data
        )

        self.local_store.save(
            action
        )

        return action