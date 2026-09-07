"""Deterministic orchestration package test."""

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
    OrchestrationStep,
    OrchestrationDefinition,
    Orchestrator,
)


def main() -> None:
    print(
        "\n[test] Starting orchestration test\n"
    )

    # --------------------------------------------------
    # Define a simple three-step orchestration.
    # --------------------------------------------------

    definition = OrchestrationDefinition(
        name="test_process",
        steps=[
            OrchestrationStep(
                step_id="inspect",
                action="inspect_wood",
                target="sensing",
                payload={
                    "source": "scan_001",
                },
            ),
            OrchestrationStep(
                step_id="design",
                action="generate_design",
                target="design",
            ),
            OrchestrationStep(
                step_id="fabricate",
                action="execute_fabrication",
                target="robot_control",
            ),
        ],
    )

    print(
        "[definition] created:",
        definition.name,
    )

    assert len(definition) == 3

    assert (
        definition.get_step(0).step_id
        == "inspect"
    )

    assert (
        definition.get_next_step(0).step_id
        == "design"
    )

    assert (
        definition.get_next_step(2)
        is None
    )

    # --------------------------------------------------
    # Validate invalid orchestration indexes.
    # --------------------------------------------------

    try:
        definition.get_step(-1)

        raise AssertionError(
            "Negative step index was accepted."
        )

    except IndexError as error:
        print(
            "[definition] negative index blocked:",
            error,
        )

    try:
        definition.get_step(3)

        raise AssertionError(
            "Out-of-range step index was accepted."
        )

    except IndexError as error:
        print(
            "[definition] high index blocked:",
            error,
        )

    try:
        definition.get_next_step(-1)

        raise AssertionError(
            "Negative next-step index was accepted."
        )

    except IndexError as error:
        print(
            "[definition] negative next index blocked:",
            error,
        )

    # --------------------------------------------------
    # Create isolated persistent master storage.
    # --------------------------------------------------

    with tempfile.TemporaryDirectory() as temp_dir:
        action_store = ActionStore(
            root=Path(temp_dir)
            / "actions"
        )

        orchestrator = Orchestrator(
            action_store=action_store
        )

        # --------------------------------------------------
        # Invalid metadata must be rejected explicitly.
        # --------------------------------------------------

        try:
            orchestrator.start(
                definition=definition,
                metadata="invalid",
            )

            raise AssertionError(
                "Invalid metadata was accepted."
            )

        except TypeError as error:
            print(
                "[orchestrator] invalid metadata blocked:",
                error,
            )

        assert (
            action_store.list_actions()
            == []
        )

        # --------------------------------------------------
        # Start orchestration.
        #
        # Only step 0 should become pending.
        # --------------------------------------------------

        action_1 = orchestrator.start(
            definition=definition,
            payload={
                "request_id": "request_001",
            },
            metadata={
                "project": "test_project",
            },
        )

        print(
            "\n[orchestrator] action 1 created:",
            action_1.to_dict(),
        )

        assert (
            action_1.status
            == ActionStatus.PENDING
        )

        assert (
            action_1.action
            == "inspect_wood"
        )

        assert (
            action_1.target
            == "sensing"
        )

        assert (
            action_1.payload["source"]
            == "scan_001"
        )

        assert (
            action_1.payload["request_id"]
            == "request_001"
        )

        assert (
            action_1.metadata["project"]
            == "test_project"
        )

        assert (
            action_1.metadata[
                "orchestration_name"
            ]
            == "test_process"
        )

        assert (
            action_1.metadata[
                "orchestration_step_id"
            ]
            == "inspect"
        )

        assert (
            action_1.metadata[
                "orchestration_step_index"
            ]
            == 0
        )

        orchestration_id = (
            action_1.metadata[
                "orchestration_id"
            ]
        )

        assert orchestration_id

        stored_actions = (
            action_store.list_actions()
        )

        assert len(stored_actions) == 1

        print(
            "[store] only first step released"
        )

        # --------------------------------------------------
        # A pending action must NOT advance orchestration.
        # --------------------------------------------------

        try:
            orchestrator.advance(
                definition=definition,
                completed_action=action_1,
            )

            raise AssertionError(
                "Pending action advanced orchestration."
            )

        except RuntimeError as error:
            print(
                "[orchestrator] premature advance blocked:",
                error,
            )

        assert (
            len(
                action_store.list_actions()
            )
            == 1
        )

        # --------------------------------------------------
        # Complete action 1 using normal ActionStore
        # lifecycle.
        # --------------------------------------------------

        sensing_agent = Agent(
            agent_id="sensing_agent_01",
            roles=[
                "sensing",
            ],
        )

        action_store.claim(
            action_id=action_1.action_id,
            agent=sensing_agent,
        )

        action_store.mark_running(
            action_id=action_1.action_id,
            agent=sensing_agent,
        )

        completed_1 = (
            action_store.mark_terminal(
                action_id=action_1.action_id,
                agent=sensing_agent,
                status=ActionStatus.COMPLETED,
            )
        )

        print(
            "\n[store] action 1 completed:",
            completed_1.to_dict(),
        )

        # --------------------------------------------------
        # Advance to step 1.
        # --------------------------------------------------

        action_2 = orchestrator.advance(
            definition=definition,
            completed_action=completed_1,
            payload={
                "inspection_result": "accepted",
            },
        )

        assert action_2 is not None

        print(
            "[orchestrator] action 2 created:",
            action_2.to_dict(),
        )

        assert (
            action_2.status
            == ActionStatus.PENDING
        )

        assert (
            action_2.action
            == "generate_design"
        )

        assert (
            action_2.target
            == "design"
        )

        assert (
            action_2.metadata[
                "orchestration_id"
            ]
            == orchestration_id
        )

        assert (
            action_2.metadata[
                "orchestration_step_id"
            ]
            == "design"
        )

        assert (
            action_2.metadata[
                "orchestration_step_index"
            ]
            == 1
        )

        assert (
            action_2.metadata[
                "previous_action_id"
            ]
            == action_1.action_id
        )

        assert (
            action_2.payload[
                "inspection_result"
            ]
            == "accepted"
        )

        assert (
            len(
                action_store.list_actions()
            )
            == 2
        )

        # --------------------------------------------------
        # Complete action 2.
        # --------------------------------------------------

        design_agent = Agent(
            agent_id="design_agent_01",
            roles=[
                "design",
            ],
        )

        action_store.claim(
            action_id=action_2.action_id,
            agent=design_agent,
        )

        action_store.mark_running(
            action_id=action_2.action_id,
            agent=design_agent,
        )

        completed_2 = (
            action_store.mark_terminal(
                action_id=action_2.action_id,
                agent=design_agent,
                status=ActionStatus.COMPLETED,
            )
        )

        # --------------------------------------------------
        # Advance to final step.
        # --------------------------------------------------

        action_3 = orchestrator.advance(
            definition=definition,
            completed_action=completed_2,
        )

        assert action_3 is not None

        print(
            "\n[orchestrator] action 3 created:",
            action_3.to_dict(),
        )

        assert (
            action_3.action
            == "execute_fabrication"
        )

        assert (
            action_3.target
            == "robot_control"
        )

        assert (
            action_3.metadata[
                "orchestration_id"
            ]
            == orchestration_id
        )

        assert (
            action_3.metadata[
                "orchestration_step_id"
            ]
            == "fabricate"
        )

        assert (
            action_3.metadata[
                "orchestration_step_index"
            ]
            == 2
        )

        assert (
            action_3.metadata[
                "previous_action_id"
            ]
            == action_2.action_id
        )

        # --------------------------------------------------
        # Complete final action.
        # --------------------------------------------------

        robot_agent = Agent(
            agent_id="robot_agent_01",
            roles=[
                "robot_control",
            ],
        )

        action_store.claim(
            action_id=action_3.action_id,
            agent=robot_agent,
        )

        action_store.mark_running(
            action_id=action_3.action_id,
            agent=robot_agent,
        )

        completed_3 = (
            action_store.mark_terminal(
                action_id=action_3.action_id,
                agent=robot_agent,
                status=ActionStatus.COMPLETED,
            )
        )

        # --------------------------------------------------
        # Final step must terminate orchestration.
        # --------------------------------------------------

        next_action = orchestrator.advance(
            definition=definition,
            completed_action=completed_3,
        )

        assert next_action is None

        assert (
            len(
                action_store.list_actions()
            )
            == 3
        )

        print(
            "\n[orchestrator] final step reached"
        )

        print(
            "[orchestrator] no further action released"
        )

    print(
        "\n[test] Orchestration test passed\n"
    )


if __name__ == "__main__":
    main()