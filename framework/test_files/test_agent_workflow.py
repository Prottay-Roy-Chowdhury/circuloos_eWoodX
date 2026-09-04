from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.communication.core import (
    Action,
    ActionStatus,
    Agent,
)

from framework.communication.storage import (
    ActionStore,
    AgentActionStore,
)

from framework.communication.transport import (
    TCPClient,
)

from framework.communication.workflow import (
    AgentWorkflowHandler,
    WorkflowClient,
    WorkflowHandler,
)


# --------------------------------------------------
# TEST PATHS
# --------------------------------------------------

TEST_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "workflow_local"
)

MASTER_ROOT = (
    TEST_ROOT
    / "master"
)

AGENT_ROOT = (
    TEST_ROOT
    / "agent"
)


shutil.rmtree(
    TEST_ROOT,
    ignore_errors=True,
)


# --------------------------------------------------
# DIRECT TEST CLIENT
# --------------------------------------------------

class DirectTCPClient(
    TCPClient
):
    """
    Test-only TCPClient replacement.

    Requests are forwarded directly to the workflow
    handler without opening a socket.
    """

    def __init__(
        self,
        handler: WorkflowHandler,
    ):
        super().__init__(
            host="127.0.0.1",
            port=5005,
        )

        self.handler = handler

    def send(
        self,
        message,
    ):
        return self.handler.handle(
            message
        )


# --------------------------------------------------
# MASTER
# --------------------------------------------------

master_store = ActionStore(
    root=MASTER_ROOT
)

master_handler = WorkflowHandler(
    action_store=master_store
)


# --------------------------------------------------
# AGENT
# --------------------------------------------------

agent = Agent(
    agent_id="design_pc_01",
    roles=[
        "design",
    ],
)

agent_store = AgentActionStore(
    root=AGENT_ROOT,
    agent=agent,
)

direct_tcp_client = DirectTCPClient(
    handler=master_handler
)

workflow_client = WorkflowClient(
    tcp_client=direct_tcp_client,
    agent=agent,
    local_store=agent_store,
)

agent_handler = AgentWorkflowHandler(
    local_store=agent_store,
    workflow_client=workflow_client,
)


# --------------------------------------------------
# CREATE MASTER ACTION
# --------------------------------------------------

action = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": "scan_001",
    },
)

master_store.save(
    action
)


print(
    "[master] created:",
    action.to_dict()
)


assert (
    action.status
    == ActionStatus.PENDING
)


# --------------------------------------------------
# AGENT CLAIMS ACTION
# --------------------------------------------------

claimed_action = (
    workflow_client.claim_next()
)


assert claimed_action is not None

assert (
    claimed_action.status
    == ActionStatus.CLAIMED
)

assert (
    claimed_action.claimed_by
    == agent.agent_id
)

assert agent_store.exists(
    claimed_action.action_id
)

assert not agent_store.is_consumed(
    claimed_action.action_id
)


print(
    "[agent] claimed:",
    claimed_action.to_dict()
)


# --------------------------------------------------
# VERIFY MASTER CLAIMED STATE
# --------------------------------------------------

master_claimed = master_store.load(
    claimed_action.action_id
)


assert (
    master_claimed.status
    == ActionStatus.CLAIMED
)


print(
    "[master] claimed:",
    master_claimed.to_dict()
)


# --------------------------------------------------
# LOCAL SOFTWARE CONSUMES ACTION
# --------------------------------------------------

consume_response = (
    agent_handler.handle(
        {
            "command": "consume_action",
        }
    )
)


print(
    "[agent-handler] consume:",
    consume_response
)


assert (
    consume_response["status"]
    == "ok"
)

assert (
    consume_response["trigger"]
    is True
)

assert (
    consume_response["action"]["action_id"]
    == claimed_action.action_id
)


# --------------------------------------------------
# VERIFY LOCAL CONSUMED STATE
# --------------------------------------------------

assert agent_store.is_consumed(
    claimed_action.action_id
)


print(
    "[agent-store] consumed:",
    agent_store.load(
        claimed_action.action_id
    )
)


# --------------------------------------------------
# VERIFY MASTER RUNNING STATE
# --------------------------------------------------

master_running = master_store.load(
    claimed_action.action_id
)


assert (
    master_running.status
    == ActionStatus.RUNNING
)

assert (
    master_running.claimed_by
    == agent.agent_id
)


print(
    "[master] running:",
    master_running.to_dict()
)


# --------------------------------------------------
# REPEATED CONSUME
# --------------------------------------------------

second_response = (
    agent_handler.handle(
        {
            "command": "consume_action",
        }
    )
)


print(
    "[agent-handler] repeated consume:",
    second_response
)


assert (
    second_response["status"]
    == "ok"
)

assert (
    second_response["trigger"]
    is False
)

assert (
    second_response["action"]
    is None
)


# --------------------------------------------------
# MASTER MUST REMAIN RUNNING
# --------------------------------------------------

master_after_repeat = (
    master_store.load(
        claimed_action.action_id
    )
)


assert (
    master_after_repeat.status
    == ActionStatus.RUNNING
)


print()
print(
    "[test] Agent workflow passed"
)