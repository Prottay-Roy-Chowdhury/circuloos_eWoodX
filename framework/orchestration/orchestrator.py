"""Sequential project-level orchestration."""

from typing import Any, Dict
from uuid import uuid4

from framework.communication.core import (
    Action,
    ActionStatus,
)

from framework.communication.storage import (
    ActionStore,
)

from framework.orchestration.definition import (
    OrchestrationDefinition,
)


class Orchestrator:
    """
    Release actions from a sequential orchestration.

    The orchestrator decides which action becomes
    eligible next.

    Distributed claiming, polling, consumption,
    execution-state synchronization, and transport
    remain responsibilities of the communication
    framework.
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

        self.action_store = (
            action_store
        )

    def start(
        self,
        definition: OrchestrationDefinition,
        payload: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Action:
        """
        Start an orchestration.

        Only the first orchestration step becomes
        a pending distributed Action.
        """

        if not isinstance(
            definition,
            OrchestrationDefinition,
        ):
            raise TypeError(
                "definition must be "
                "an OrchestrationDefinition."
            )

        orchestration_id = str(
            uuid4()
        )

        return self._create_action(
            definition=definition,
            orchestration_id=orchestration_id,
            step_index=0,
            payload=payload,
            metadata=metadata,
        )

    def advance(
        self,
        definition: OrchestrationDefinition,
        completed_action: Action,
        payload: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Action | None:
        """
        Release the next action in the orchestration.

        The previous action must already be completed.

        Returns None when the completed action
        represents the final orchestration step.
        """

        if not isinstance(
            definition,
            OrchestrationDefinition,
        ):
            raise TypeError(
                "definition must be "
                "an OrchestrationDefinition."
            )

        if not isinstance(
            completed_action,
            Action,
        ):
            raise TypeError(
                "completed_action must be an Action."
            )

        if (
            completed_action.status
            != ActionStatus.COMPLETED
        ):
            raise RuntimeError(
                "Only a completed action can "
                "advance an orchestration."
            )

        orchestration_id = (
            completed_action.metadata.get(
                "orchestration_id"
            )
        )

        orchestration_name = (
            completed_action.metadata.get(
                "orchestration_name"
            )
        )

        step_index = (
            completed_action.metadata.get(
                "orchestration_step_index"
            )
        )

        if not orchestration_id:
            raise RuntimeError(
                "Action does not contain "
                "orchestration_id."
            )

        if (
            orchestration_name
            != definition.name
        ):
            raise RuntimeError(
                "Action belongs to another "
                "orchestration definition."
            )

        if not isinstance(
            step_index,
            int,
        ):
            raise RuntimeError(
                "Action does not contain a valid "
                "orchestration_step_index."
            )

        current_step = (
            definition.get_step(
                step_index
            )
        )

        recorded_step_id = (
            completed_action.metadata.get(
                "orchestration_step_id"
            )
        )

        if (
            recorded_step_id
            != current_step.step_id
        ):
            raise RuntimeError(
                "Action orchestration step metadata "
                "does not match the definition."
            )

        next_index = (
            step_index + 1
        )

        if (
            next_index
            >= len(definition)
        ):
            return None

        existing_successor = (
            self._find_successor(
                definition=definition,
                completed_action=completed_action,
                orchestration_id=orchestration_id,
                step_index=next_index,
            )
        )

        if existing_successor is not None:
            return existing_successor

        next_metadata = dict(
            metadata
            or {}
        )

        next_metadata[
            "previous_action_id"
        ] = (
            completed_action.action_id
        )

        return self._create_action(
            definition=definition,
            orchestration_id=orchestration_id,
            step_index=next_index,
            payload=payload,
            metadata=next_metadata,
        )

    def _find_successor(
        self,
        definition: OrchestrationDefinition,
        completed_action: Action,
        orchestration_id: str,
        step_index: int,
    ) -> Action | None:
        """
        Find an already released successor action.

        A completed action may release at most one
        successor action.
        """

        successors = []

        for action in (
            self.action_store
            .list_actions()
        ):
            if (
                action.metadata.get(
                    "previous_action_id"
                )
                != completed_action.action_id
            ):
                continue

            successors.append(
                action
            )

        if not successors:
            return None

        if len(successors) > 1:
            raise RuntimeError(
                "Multiple successor actions exist "
                "for the same completed action."
            )

        successor = successors[0]

        expected_step = (
            definition.get_step(
                step_index
            )
        )

        if (
            successor.metadata.get(
                "orchestration_id"
            )
            != orchestration_id
        ):
            raise RuntimeError(
                "Existing successor belongs to "
                "another orchestration."
            )

        if (
            successor.metadata.get(
                "orchestration_name"
            )
            != definition.name
        ):
            raise RuntimeError(
                "Existing successor belongs to "
                "another orchestration definition."
            )

        if (
            successor.metadata.get(
                "orchestration_step_index"
            )
            != step_index
        ):
            raise RuntimeError(
                "Existing successor has an invalid "
                "orchestration step index."
            )

        if (
            successor.metadata.get(
                "orchestration_step_id"
            )
            != expected_step.step_id
        ):
            raise RuntimeError(
                "Existing successor does not match "
                "the expected orchestration step."
            )

        return successor

    def _create_action(
        self,
        definition: OrchestrationDefinition,
        orchestration_id: str,
        step_index: int,
        payload: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Action:
        """
        Create and persist an action for one
        orchestration step.
        """

        step = definition.get_step(
            step_index
        )

        action_payload = dict(
            step.payload
        )

        if payload is not None:
            if not isinstance(
                payload,
                dict,
            ):
                raise TypeError(
                    "payload must be a dictionary "
                    "or None."
                )

            action_payload.update(
                payload
            )

        if (
            metadata is not None
            and not isinstance(
                metadata,
                dict,
            )
        ):
            raise TypeError(
                "metadata must be a dictionary "
                "or None."
            )

        action_metadata = dict(
            metadata
            or {}
        )

        action_metadata.update(
            {
                "orchestration_id": (
                    orchestration_id
                ),
                "orchestration_name": (
                    definition.name
                ),
                "orchestration_step_id": (
                    step.step_id
                ),
                "orchestration_step_index": (
                    step_index
                ),
            }
        )

        action = Action(
            action=step.action,
            target=step.target,
            payload=action_payload,
            metadata=action_metadata,
        )

        self.action_store.save(
            action
        )

        return action