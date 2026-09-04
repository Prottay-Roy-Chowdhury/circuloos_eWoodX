"""Generic distributed workflow request handler."""

from typing import Any, Dict

from framework.communication.core import (
    ActionStatus,
    Agent,
)

from framework.communication.storage import (
    ActionStore,
)

from framework.communication.workflow.coordinator import (
    Coordinator,
)


class WorkflowHandler:
    """
    Handle generic distributed workflow requests.

    This handler contains no project-specific knowledge.
    """

    def __init__(
        self,
        action_store: ActionStore,
    ):
        if not isinstance(
            action_store,
            ActionStore,
        ):
            raise TypeError(
                "action_store must be an ActionStore."
            )

        self.action_store = action_store

        self.coordinator = Coordinator(
            action_store=action_store
        )

    def handle(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle a workflow request.
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

        if command == "claim_next":
            return self._claim_next(
                request
            )
        
        if command == "mark_running":
            return self._mark_running(
                request
            )

        return {
            "status": "error",
            "message": (
                f"Unknown command: {command}"
            ),
        }

    def _claim_next(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        agent_data = request.get(
            "agent"
        )

        if not isinstance(
            agent_data,
            dict,
        ):
            return {
                "status": "error",
                "message": "Missing agent data.",
            }

        try:
            agent = Agent.from_dict(
                agent_data
            )

            action = (
                self.coordinator.claim_next(
                    agent
                )
            )

            return {
                "status": "ok",
                "action": (
                    action.to_dict()
                    if action is not None
                    else None
                ),
            }

        except Exception as error:
            return {
                "status": "error",
                "message": str(
                    error
                ),
            }

    

    def _mark_running(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Mark a claimed action as running.
        """

        agent_data = request.get(
            "agent"
        )

        if not isinstance(
            agent_data,
            dict,
        ):
            return {
                "status": "error",
                "message": "Missing agent data.",
            }

        action_id = str(
            request.get(
                "action_id",
                "",
            )
        ).strip()

        if not action_id:
            return {
                "status": "error",
                "message": "Missing action_id.",
            }

        try:
            agent = Agent.from_dict(
                agent_data
            )

            action = (
                self.action_store
                .mark_running(
                    action_id=action_id,
                    agent=agent,
                )
            )

            return {
                "status": "ok",
                "action": action.to_dict(),
            }

        except Exception as error:
            return {
                "status": "error",
                "message": str(
                    error
                ),
            }