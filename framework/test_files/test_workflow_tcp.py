from pathlib import Path
import shutil
import sys
import threading
import time


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
    TCPServer,
)

from framework.communication.workflow import (
    AgentWorkflowHandler,
    WorkflowClient,
    WorkflowHandler,
)


# --------------------------------------------------
# TEST CONFIG
# --------------------------------------------------

HOST = "127.0.0.1"
MASTER_PORT = 5105

TEST_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "workflow_tcp"
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
# MASTER
# --------------------------------------------------

master_store = ActionStore(
    root=MASTER_ROOT
)

master_handler = WorkflowHandler(
    action_store=master_store
)


master_server = TCPServer(
    handler=master_handler.handle,
    host=HOST,
    port=MASTER_PORT,
)


server_thread = threading.Thread(
    target=master_server.start,
    daemon=True,
)

server_thread.start()


# Give the listening socket a moment to start.
time.sleep(
    0.5
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


tcp_client = TCPClient(
    host=HOST,
    port=MASTER_PORT,
)


workflow_client = WorkflowClient(
    tcp_client=tcp_client,
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
        "source_artifact_id": "scan_tcp_001",
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
# AGENT CLAIMS THROUGH REAL TCP
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


print(
    "[agent] claimed through TCP:",
    claimed_action.to_dict()
)


# --------------------------------------------------
# VERIFY LOCAL CLAIMED ACTION
# --------------------------------------------------

assert agent_store.exists(
    claimed_action.action_id
)

assert not agent_store.is_consumed(
    claimed_action.action_id
)


local_claimed = agent_store.load(
    claimed_action.action_id
)


print(
    "[agent-store] claimed:",
    local_claimed
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
# CONSUME LOCALLY
#
# AgentWorkflowHandler:
#     mark consumed locally
#           ↓
#     WorkflowClient.mark_running()
#           ↓
#     real TCP
#           ↓
#     master WorkflowHandler
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

assert (
    consume_response["action"]["status"]
    == ActionStatus.RUNNING.value
)


# --------------------------------------------------
# VERIFY LOCAL CONSUMED STATE
# --------------------------------------------------

assert agent_store.is_consumed(
    claimed_action.action_id
)


local_consumed = agent_store.load(
    claimed_action.action_id
)


print(
    "[agent-store] consumed:",
    local_consumed
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
# REPEATED LOCAL CONSUME
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


# --------------------------------------------------
# STOP SERVER
# --------------------------------------------------

master_server.stop()

server_thread.join(
    timeout=2.0
)


print()
print(
    "[test] TCP workflow passed"
)