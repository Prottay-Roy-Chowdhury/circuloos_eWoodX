"""Agent-side workflow polling."""

import threading
from typing import Any, Dict

from framework.communication.storage import (
    AgentActionStore,
)

from framework.communication.workflow.client import (
    WorkflowClient,
)


class AgentPoller:
    """
    Poll the master for work when the agent has no
    active local action.

    The polling behavior follows the proven DECO2
    agent pattern:

        check local active action
            ↓
        active exists -> return it
            ↓
        otherwise ask master
            ↓
        claim eligible action
            ↓
        persist locally
    """

    def __init__(
        self,
        workflow_client: WorkflowClient,
        local_store: AgentActionStore,
        interval: float = 1.0,
    ):
        if not isinstance(
            workflow_client,
            WorkflowClient,
        ):
            raise TypeError(
                "workflow_client must be a WorkflowClient."
            )

        if not isinstance(
            local_store,
            AgentActionStore,
        ):
            raise TypeError(
                "local_store must be an AgentActionStore."
            )

        if (
            workflow_client.agent.agent_id
            != local_store.agent.agent_id
        ):
            raise ValueError(
                "workflow_client and local_store "
                "must belong to the same agent."
            )

        self.workflow_client = (
            workflow_client
        )

        self.local_store = (
            local_store
        )

        self.interval = float(
            interval
        )

        if self.interval <= 0:
            raise ValueError(
                "interval must be greater than zero."
            )

        self._stop_event = (
            threading.Event()
        )

        self._thread = None

        self._lock = (
            threading.Lock()
        )

    def poll_once(
        self,
    ) -> Dict[str, Any] | None:
        """
        Perform one polling cycle.

        Returns:
            existing active local action,
            newly claimed local action,
            or None when no action is available.
        """

        # ------------------------------------------
        # DECO2 parity:
        # never claim another action while one
        # remains active locally.
        # ------------------------------------------

        local_action = (
            self.local_store
            .find_active()
        )

        if local_action is not None:
            return local_action

        # ------------------------------------------
        # No local active action.
        # Ask the master for work.
        #
        # WorkflowClient.claim_next() already:
        #   1. requests an eligible action
        #   2. claims it on the master
        #   3. saves it locally
        # ------------------------------------------

        action = (
            self.workflow_client
            .claim_next()
        )

        if action is None:
            return None

        return self.local_store.load(
            action.action_id
        )

    def start(
        self,
    ) -> bool:
        """
        Start one background polling thread.
        """

        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return False

            self._stop_event.clear()

            self._thread = threading.Thread(
                target=self._run,
                name=(
                    "agent-workflow-poller-"
                    f"{self.local_store.agent.agent_id}"
                ),
                daemon=True,
            )

            self._thread.start()

        return True

    def stop(
        self,
        join_timeout: float = 2.0,
    ) -> bool:
        """
        Stop the background polling thread.
        """

        with self._lock:
            thread = self._thread

            if (
                thread is None
                or not thread.is_alive()
            ):
                self._thread = None
                return False

            self._stop_event.set()

        thread.join(
            timeout=max(
                0.0,
                float(join_timeout),
            )
        )

        with self._lock:
            if not thread.is_alive():
                self._thread = None

        return True

    def _run(
        self,
    ) -> None:
        """
        Background polling loop.
        """

        while not self._stop_event.is_set():
            try:
                self.poll_once()

            except Exception as error:
                print(
                    "[agent-poller] polling error:",
                    error,
                )

            self._stop_event.wait(
                self.interval
            )