"""Orchestration successor idempotency test."""

from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.communication.core import (  # noqa: E402
    ActionStatus,
    Agent,
)

from framework.communication.storage import (  # noqa: E402
    ActionStore,
)

from framework.orchestration import (  # noqa: E402
    OrchestrationDefinition,
    OrchestrationStep,
    Orchestrator,
)


def main() -> None:
    print(
        "\n[test] Starting orchestration "
        "idempotency test\n"
    )

    definition = OrchestrationDefinition(
        name="idempotency_test",
        steps=[
            OrchestrationStep(
                step_id="inspect",
                action="inspect_wood",
                target="sensing",
            ),
            OrchestrationStep(
                step_id="design",
                action="generate_design",
                target="design",
            ),
        ],
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        action_store = ActionStore(
            root=Path(temp_dir)
            / "actions"
        )

        orchestrator = Orchestrator(
            action_store=action_store
        )

        # ----------------------------------------------
        # Release first action.
        # ----------------------------------------------

        action_1 = orchestrator.start(
            definition=definition
        )

        print(
            "[orchestrator] action 1:",
            action_1.to_dict(),
        )

        assert (
            len(
                action_store.list_actions()
            )
            == 1
        )

        # ----------------------------------------------
        # Complete first action.
        # ----------------------------------------------

        agent = Agent(
            agent_id="sensing_agent_01",
            roles=[
                "sensing",
            ],
        )

        action_store.claim(
            action_id=action_1.action_id,
            agent=agent,
        )

        action_store.mark_running(
            action_id=action_1.action_id,
            agent=agent,
        )

        completed_1 = (
            action_store.mark_terminal(
                action_id=action_1.action_id,
                agent=agent,
                status=ActionStatus.COMPLETED,
            )
        )

        # ----------------------------------------------
        # First advancement creates successor.
        # ----------------------------------------------

        action_2_first = (
            orchestrator.advance(
                definition=definition,
                completed_action=completed_1,
                payload={
                    "attempt": "first",
                },
            )
        )

        assert (
            action_2_first
            is not None
        )

        print(
            "\n[orchestrator] first advance:",
            action_2_first.to_dict(),
        )

        assert (
            len(
                action_store.list_actions()
            )
            == 2
        )

        # ----------------------------------------------
        # Retry the SAME completed action.
        #
        # Even though different payload/metadata are
        # supplied, the already persisted successor
        # must be returned.
        # ----------------------------------------------

        action_2_retry = (
            orchestrator.advance(
                definition=definition,
                completed_action=completed_1,
                payload={
                    "attempt": "retry",
                },
                metadata={
                    "retry": True,
                },
            )
        )

        assert (
            action_2_retry
            is not None
        )

        print(
            "[orchestrator] retry advance:",
            action_2_retry.to_dict(),
        )

        # ----------------------------------------------
        # Same successor must be returned.
        # ----------------------------------------------

        assert (
            action_2_retry.action_id
            == action_2_first.action_id
        )

        # No duplicate action may have been created.

        stored_actions = (
            action_store.list_actions()
        )

        assert len(stored_actions) == 2

        successors = [
            action
            for action in stored_actions
            if action.metadata.get(
                "previous_action_id"
            )
            == action_1.action_id
        ]

        assert len(successors) == 1

        assert (
            successors[0].action_id
            == action_2_first.action_id
        )

        # Retry arguments must not mutate the already
        # persisted successor.

        assert (
            action_2_retry.payload[
                "attempt"
            ]
            == "first"
        )

        assert (
            "retry"
            not in action_2_retry.metadata
        )

        print(
            "\n[orchestrator] duplicate "
            "successor blocked"
        )

        print(
            "[store] successor count:",
            len(successors),
        )

    print(
        "\n[test] Orchestration idempotency "
        "test passed\n"
    )


if __name__ == "__main__":
    main()