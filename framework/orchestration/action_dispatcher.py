"""Generic local action dispatching."""

from typing import Any, Callable, Dict

from framework.communication.core import (
    Action,
)


ActionHandler = Callable[
    [Action],
    Any,
]


class ActionDispatcher:
    """
    Dispatch a distributed Action to a registered
    local execution handler.

    The dispatcher contains no communication,
    transport, agent-lifecycle, storage, or
    project-specific logic.
    """

    def __init__(
        self,
    ) -> None:

        self._handlers: Dict[
            str,
            ActionHandler,
        ] = {}

    def register(
        self,
        action: str,
        handler: ActionHandler,
    ) -> None:
        """
        Register one local handler for an action.
        """

        action_name = self._normalize_action(
            action
        )

        if not callable(
            handler
        ):
            raise TypeError(
                "handler must be callable."
            )

        if action_name in self._handlers:
            raise ValueError(
                "Handler already registered "
                f"for action: {action_name}"
            )

        self._handlers[
            action_name
        ] = handler

    def dispatch(
        self,
        action: Action,
    ) -> Any:
        """
        Dispatch an Action to its registered
        local execution handler.
        """

        if not isinstance(
            action,
            Action,
        ):
            raise TypeError(
                "action must be an Action."
            )

        handler = self._handlers.get(
            action.action
        )

        if handler is None:
            raise KeyError(
                "No handler registered "
                f"for action: {action.action}"
            )

        return handler(
            action
        )

    @staticmethod
    def _normalize_action(
        action: str,
    ) -> str:

        action_name = str(
            action or ""
        ).strip().lower()

        if not action_name:
            raise ValueError(
                "action cannot be empty."
            )

        return action_name