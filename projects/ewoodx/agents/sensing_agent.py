from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.communication.core import (
    Agent,
)

from framework.communication.storage import (
    AgentActionStore,
)

from framework.communication.transport import (
    TCPClient,
    TCPServer,
)

from framework.communication.workflow import (
    AgentPoller,
    AgentWorkflowHandler,
    WorkflowClient,
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
    SENSING_AGENT_HOST,
    SENSING_AGENT_ID,
    SENSING_AGENT_POLL_INTERVAL,
    SENSING_AGENT_PORT,
    SENSING_AGENT_ROLES,
)

from projects.ewoodx.orchestration.agent_handler import (
    EWoodXAgentHandler,
)


def run_sensing_agent(
    workspace: WorkspacePaths,
) -> None:
    """
    Start the eWoodX sensing agent for one workspace.

    The project side composes the generic communication
    framework for the deployed sensing agent.
    """

    if not isinstance(
        workspace,
        WorkspacePaths,
    ):
        raise TypeError(
            "workspace must be a WorkspacePaths instance."
        )

    # ---------------------------------------------------------
    # Agent identity
    # ---------------------------------------------------------

    agent = Agent(
        agent_id=SENSING_AGENT_ID,
        roles=SENSING_AGENT_ROLES,
    )

    # ---------------------------------------------------------
    # Agent-local persistent state
    # ---------------------------------------------------------

    agent_runtime_root = (
        workspace.root
        / AGENTS_RUNTIME_DIRECTORY
        / agent.agent_id
    )

    local_store = AgentActionStore(
        root=agent_runtime_root,
        agent=agent,
    )

    # ---------------------------------------------------------
    # Master connection
    # ---------------------------------------------------------

    master_client = TCPClient(
        host=MASTER_HOST,
        port=MASTER_PORT,
    )

    workflow_client = WorkflowClient(
        tcp_client=master_client,
        agent=agent,
        local_store=local_store,
    )

    # ---------------------------------------------------------
    # Master polling
    # ---------------------------------------------------------

    poller = AgentPoller(
        workflow_client=workflow_client,
        local_store=local_store,
        interval=SENSING_AGENT_POLL_INTERVAL,
    )

    # ---------------------------------------------------------
    # Local execution API
    # ---------------------------------------------------------

    agent_handler = AgentWorkflowHandler(
        local_store=local_store,
        workflow_client=workflow_client,
    )

    project_handler = EWoodXAgentHandler(
        agent_handler=agent_handler,
        master_client=master_client,
    )

    local_server = TCPServer(
        handler=project_handler.handle,
        host=SENSING_AGENT_HOST,
        port=SENSING_AGENT_PORT,
    )

    # ---------------------------------------------------------
    # Start
    # ---------------------------------------------------------

    print()
    print(
        "[eWoodX] Starting sensing agent"
    )

    print(
        f"[eWoodX] Agent ID: {agent.agent_id}"
    )

    print(
        f"[eWoodX] Roles: {agent.roles}"
    )

    print(
        f"[eWoodX] Workspace: {workspace.root}"
    )

    print(
        "[eWoodX] Runtime state: "
        f"{agent_runtime_root}"
    )

    print(
        "[eWoodX] Master: "
        f"{MASTER_HOST}:{MASTER_PORT}"
    )

    print(
        "[eWoodX] Local API: "
        f"{SENSING_AGENT_HOST}:{SENSING_AGENT_PORT}"
    )

    poller.start()

    try:

        local_server.start()

    finally:

        print()
        print(
            "[eWoodX] Stopping sensing agent"
        )

        poller.stop()
        local_server.stop()


def main(
) -> None:
    """
    Start the sensing agent using the current
    eWoodX workspace.
    """

    workspace = load_workspace(
        project_root=EWOODX_REPOSITORY_ROOT,
    )

    run_sensing_agent(
        workspace=workspace,
    )


if __name__ == "__main__":
    main()