"""Distributed action coordination."""

from framework.communication.core import (
    Action,
    Agent,
)

from framework.communication.storage import (
    ActionStore,
)


class Coordinator:
    """
    Coordinate distributed actions using an ActionStore.
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

    def claim_next(
        self,
        agent: Agent,
    ) -> Action | None:
        """
        Find and claim the next pending action
        that the agent can handle.
        """

        if not isinstance(
            agent,
            Agent,
        ):
            raise TypeError(
                "agent must be an Agent."
            )

        pending = (
            self.action_store.find_pending(
                targets=agent.roles
            )
        )

        if not pending:
            return None

        action = pending[0]

        return self.action_store.claim(
            action_id=action.action_id,
            agent=agent,
        )