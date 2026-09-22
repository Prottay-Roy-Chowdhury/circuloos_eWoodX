from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.communication.storage import (
    ActionStore,
)

from framework.communication.transport import (
    TCPServer,
)

from framework.communication.workflow import (
    WorkflowHandler,
)

from framework.orchestration import (
    Orchestrator,
)

from projects.ewoodx.config import (
    AGENTS_RUNTIME_ROOT,
    MASTER_HOST,
    MASTER_PORT,
)

from projects.ewoodx.orchestration.master_handler import (
    EWoodXMasterHandler,
)


def run_master_agent(
) -> None:
    """
    Start the eWoodX master communication runtime.
    """

    # ---------------------------------------------------------
    # Master persistent action state
    # ---------------------------------------------------------

    master_runtime_root = (
        AGENTS_RUNTIME_ROOT
        / "master"
    )

    action_store = ActionStore(
        root=master_runtime_root,
    )

    # ---------------------------------------------------------
    # Distributed workflow handler
    # ---------------------------------------------------------

    workflow_handler = WorkflowHandler(
        action_store=action_store,
    )

    # ---------------------------------------------------------
    # Project orchestration
    # ---------------------------------------------------------

    orchestrator = Orchestrator(
        action_store=action_store,
    )

    master_handler = EWoodXMasterHandler(
        workflow_handler=workflow_handler,
        orchestrator=orchestrator,
    )

    # ---------------------------------------------------------
    # Master communication server
    # ---------------------------------------------------------

    server = TCPServer(
        handler=master_handler.handle,
        host=MASTER_HOST,
        port=MASTER_PORT,
    )

    # ---------------------------------------------------------
    # Start
    # ---------------------------------------------------------

    print()
    print(
        "[eWoodX] Starting master"
    )

    print(
        "[eWoodX] Runtime state: "
        f"{master_runtime_root}"
    )

    print(
        "[eWoodX] Master API: "
        f"{MASTER_HOST}:{MASTER_PORT}"
    )

    try:

        server.start()

    finally:

        print()
        print(
            "[eWoodX] Stopping master"
        )

        server.stop()


def main(
) -> None:
    """
    Start the eWoodX master communication runtime.
    """

    run_master_agent()


if __name__ == "__main__":
    main()