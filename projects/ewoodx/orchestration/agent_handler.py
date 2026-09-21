"""eWoodX agent-side orchestration request handling."""

from typing import Any, Dict

from framework.communication.transport import (
    TCPClient,
)

from framework.communication.workflow import (
    AgentWorkflowHandler,
)


class EWoodXAgentHandler:
    """
    Compose eWoodX orchestration requests with the
    generic agent-local workflow handler.

    Project orchestration requests are forwarded to
    the master. Generic local workflow commands are
    delegated to AgentWorkflowHandler.
    """

    def __init__(
        self,
        agent_handler: AgentWorkflowHandler,
        master_client: TCPClient,
    ):
        if not isinstance(
            agent_handler,
            AgentWorkflowHandler,
        ):
            raise TypeError(
                "agent_handler must be an "
                "AgentWorkflowHandler."
            )

        if not isinstance(
            master_client,
            TCPClient,
        ):
            raise TypeError(
                "master_client must be a TCPClient."
            )

        self.agent_handler = agent_handler
        self.master_client = master_client

    def handle(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle one local request.
        """

        if not isinstance(
            request,
            dict,
        ):
            raise TypeError(
                "request must be a dictionary."
            )

        command = str(
            request.get(
                "command",
                "",
            )
        ).strip().lower()

        if command == "start_orchestration":
            return self._start_orchestration(
                request
            )

        return self.agent_handler.handle(
            request
        )

    def _start_orchestration(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Forward an eWoodX orchestration request
        to the master.
        """

        return self.master_client.send(
            request
        )