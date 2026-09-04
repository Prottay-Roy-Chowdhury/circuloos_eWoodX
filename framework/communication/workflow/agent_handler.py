"""Agent-local workflow request handler."""

from typing import Any, Dict

from framework.communication.storage import (
    AgentActionStore,
)

from framework.communication.workflow.client import (
    WorkflowClient,
)


class AgentWorkflowHandler:
    """
    Handle workflow requests from software running
    locally on an agent.

    The handler contains no transport-specific or
    project-specific logic.
    """

    def __init__(
        self,
        local_store: AgentActionStore,
        workflow_client: WorkflowClient,
    ):
        if not isinstance(
            local_store,
            AgentActionStore,
        ):
            raise TypeError(
                "local_store must be an AgentActionStore."
            )

        if not isinstance(
            workflow_client,
            WorkflowClient,
        ):
            raise TypeError(
                "workflow_client must be a WorkflowClient."
            )

        if (
            local_store.agent.agent_id
            != workflow_client.agent.agent_id
        ):
            raise ValueError(
                "local_store and workflow_client "
                "must belong to the same agent."
            )

        self.local_store = local_store
        self.workflow_client = (
            workflow_client
        )

    def handle(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle an agent-local workflow request.
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

        if not command:
            return {
                "status": "error",
                "message": "Missing command.",
            }

        if command == "consume_action":
            return self._consume_action()

        return {
            "status": "error",
            "message": (
                f"Unknown command: {command}"
            ),
        }

    def _consume_action(
        self,
    ) -> Dict[str, Any]:
        """
        Consume the current locally available action.

        Local consumption happens before the running state
        is reported to the master.
        """

        try:
            local_data = (
                self.local_store
                .find_unconsumed()
            )

            if local_data is None:
                return {
                    "status": "ok",
                    "trigger": False,
                    "action": None,
                }

            action_data = local_data.get(
                "action"
            )

            if not isinstance(
                action_data,
                dict,
            ):
                raise ValueError(
                    "Invalid local action record."
                )

            action_id = str(
                action_data.get(
                    "action_id",
                    "",
                )
            ).strip()

            if not action_id:
                raise ValueError(
                    "Local action is missing action_id."
                )

            # ------------------------------------------
            # 1. Consume locally first.
            # ------------------------------------------

            self.local_store.mark_consumed(
                action_id
            )

            # ------------------------------------------
            # 2. Report running to the master.
            # ------------------------------------------

            running_action = (
                self.workflow_client
                .mark_running(
                    action_id
                )
            )

            return {
                "status": "ok",
                "trigger": True,
                "action": (
                    running_action.to_dict()
                ),
            }

        except Exception as error:
            return {
                "status": "error",
                "message": str(
                    error
                ),
            }