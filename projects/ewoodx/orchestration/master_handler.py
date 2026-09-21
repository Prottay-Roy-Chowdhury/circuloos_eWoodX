"""eWoodX master-side orchestration request handling."""

from typing import Any, Dict

from framework.communication.workflow import (
    WorkflowHandler,
)

from framework.orchestration import (
    Orchestrator,
)

from projects.ewoodx.orchestration.definitions import (
    SENSING_ORCHESTRATION,
)


class EWoodXMasterHandler:
    """
    Compose eWoodX orchestration requests with the
    generic distributed workflow handler.
    """

    def __init__(
        self,
        workflow_handler: WorkflowHandler,
        orchestrator: Orchestrator,
    ):
        if not isinstance(
            workflow_handler,
            WorkflowHandler,
        ):
            raise TypeError(
                "workflow_handler must be a WorkflowHandler."
            )

        if not isinstance(
            orchestrator,
            Orchestrator,
        ):
            raise TypeError(
                "orchestrator must be an Orchestrator."
            )

        self.workflow_handler = workflow_handler
        self.orchestrator = orchestrator

    def handle(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle project orchestration requests and delegate
        generic workflow requests to WorkflowHandler.
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

        return self.workflow_handler.handle(
            request
        )

    def _start_orchestration(
        self,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        orchestration_name = str(
            request.get(
                "orchestration",
                "",
            )
        ).strip().lower()

        if not orchestration_name:
            return {
                "status": "error",
                "message": "Missing orchestration.",
            }

        if orchestration_name != "sensing":
            return {
                "status": "error",
                "message": (
                    "Unknown eWoodX orchestration: "
                    f"{orchestration_name}"
                ),
            }

        try:
            action = self.orchestrator.start(
                definition=SENSING_ORCHESTRATION,
            )

            return {
                "status": "ok",
                "orchestration": orchestration_name,
                "action": action.to_dict(),
            }

        except Exception as error:
            return {
                "status": "error",
                "message": str(
                    error
                ),
            }