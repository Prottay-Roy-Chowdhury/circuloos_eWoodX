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
AGENT_PORT = 6105


TEST_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "two_sided_workflow_tcp"
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


master_thread = threading.Thread(
    target=master_server.start,
    daemon=True,
)

master_thread.start()


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


master_tcp_client = TCPClient(
    host=HOST,
    port=MASTER_PORT,
)


workflow_client = WorkflowClient(
    tcp_client=master_tcp_client,
    agent=agent,
    local_store=agent_store,
)


agent_handler = AgentWorkflowHandler(
    local_store=agent_store,
    workflow_client=workflow_client,
)


agent_server = TCPServer(
    handler=agent_handler.handle,
    host=HOST,
    port=AGENT_PORT,
)


agent_thread = threading.Thread(
    target=agent_server.start,
    daemon=True,
)

agent_thread.start()


# Allow both listening sockets to start.
time.sleep(
    0.5
)


# --------------------------------------------------
# SIMULATED GRASSHOPPER CLIENT
# --------------------------------------------------

gh_client = TCPClient(
    host=HOST,
    port=AGENT_PORT,
)


# --------------------------------------------------
# CREATE MASTER ACTION
# --------------------------------------------------

action = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": "scan_two_sided_001",
    },
)


master_store.save(
    action
)


print()
print(
    "[master] created:",
    action.to_dict()
)


assert (
    action.status
    == ActionStatus.PENDING
)


# --------------------------------------------------
# AGENT CLAIMS FROM MASTER
#
# agent
#   ↓ TCP
# master
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
    "[agent] claimed:",
    claimed_action.to_dict()
)


# --------------------------------------------------
# VERIFY LOCAL CLAIM
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
# VERIFY MASTER CLAIMED
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
# GRASSHOPPER CONSUMES THROUGH AGENT TCP SERVER
#
# simulated GH
#       ↓ TCP
# agent TCPServer
#       ↓
# AgentWorkflowHandler
#       ↓
# local consumed
#       ↓
# WorkflowClient
#       ↓ TCP
# master TCPServer
#       ↓
# master running
# --------------------------------------------------

consume_response = gh_client.send(
    {
        "command": "consume_action",
    }
)


print()
print(
    "[grasshopper] consume response:",
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
# VERIFY LOCAL CONSUMED
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
# VERIFY MASTER RUNNING
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
# GRASSHOPPER SOLVES AGAIN
#
# Same behavior as repeated GH component execution.
# --------------------------------------------------

second_response = gh_client.send(
    {
        "command": "consume_action",
    }
)


print()
print(
    "[grasshopper] repeated consume:",
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
# STOP SERVERS
# --------------------------------------------------

agent_server.stop()
master_server.stop()


agent_thread.join(
    timeout=2.0
)

master_thread.join(
    timeout=2.0
)


print()
print(
    "[test] Two-sided TCP workflow passed"
)