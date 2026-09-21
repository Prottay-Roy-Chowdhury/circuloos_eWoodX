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

from framework.workspace import (
    WorkspacePaths,
    load_workspace,
)

from projects.ewoodx.config import (
    AGENTS_RUNTIME_DIRECTORY,
    EWOODX_REPOSITORY_ROOT,
    MASTER_HOST,
    MASTER_PORT,
)


def run_master_agent(
    workspace: WorkspacePaths,
) -> None:
    """
    Start the eWoodX master communication runtime
    for one workspace.
    """

    if not isinstance(
        workspace,
        WorkspacePaths,
    ):
        raise TypeError(
            "workspace must be a WorkspacePaths instance."
        )

    # ---------------------------------------------------------
    # Master persistent action state
    # ---------------------------------------------------------

    master_runtime_root = (
        workspace.root
        / AGENTS_RUNTIME_DIRECTORY
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
    # Master communication server
    # ---------------------------------------------------------

    server = TCPServer(
        handler=workflow_handler.handle,
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
        f"[eWoodX] Workspace: {workspace.root}"
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
    Start the master using the current
    eWoodX workspace.
    """

    workspace = load_workspace(
        project_root=EWOODX_REPOSITORY_ROOT,
    )

    run_master_agent(
        workspace=workspace,
    )


if __name__ == "__main__":
    main()