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

from framework.orchestration import (
    ActionDispatcher,
)


# --------------------------------------------------
# TEST CONFIG
# --------------------------------------------------

HOST = "127.0.0.1"

MASTER_PORT = 5107
AGENT_PORT = 6107


TEST_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "action_dispatcher_tcp"
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
# SENSING AGENT
# --------------------------------------------------

agent = Agent(
    agent_id="sensing_pc_01",
    roles=[
        "sensing",
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
# LOCAL EXECUTION CLIENT
#
# This represents software running on the sensing
# side. Today it may be Python. Later another local
# execution endpoint could use the same agent API.
# --------------------------------------------------

execution_client = TCPClient(
    host=HOST,
    port=AGENT_PORT,
)


# --------------------------------------------------
# DUMMY SENSING HANDLER
# --------------------------------------------------

executed_action = None


def handle_sense_timber(
    action: Action,
):
    global executed_action

    executed_action = action

    print(
        "[sensing-handler] executing:",
        action.to_dict(),
    )

    return {
        "equipment": action.payload.get(
            "equipment"
        ),
        "result": "timber_sensed",
    }


# --------------------------------------------------
# ACTION DISPATCHER
# --------------------------------------------------

dispatcher = ActionDispatcher()

dispatcher.register(
    action="sense_timber",
    handler=handle_sense_timber,
)


# --------------------------------------------------
# CREATE MASTER ACTION
# --------------------------------------------------

action = Action(
    action="sense_timber",
    target="sensing",
    payload={
        "equipment": "webcam",
    },
)


master_store.save(
    action
)


print()
print(
    "[master] created:",
    action.to_dict(),
)


assert (
    action.status
    == ActionStatus.PENDING
)


# --------------------------------------------------
# AGENT CLAIMS FROM MASTER
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


print()
print(
    "[agent] claimed:",
    claimed_action.to_dict(),
)


# --------------------------------------------------
# LOCAL EXECUTION ENDPOINT CONSUMES ACTION
#
# execution endpoint
#       ↓ TCP
# sensing agent
#       ↓
# AgentWorkflowHandler
#       ↓
# local consumed
#       ↓
# master RUNNING
# --------------------------------------------------

consume_response = execution_client.send(
    {
        "command": "consume_action",
    }
)


print()
print(
    "[executor] consume response:",
    consume_response,
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
    consume_response["action"]["status"]
    == ActionStatus.RUNNING.value
)


# --------------------------------------------------
# RECONSTRUCT DISTRIBUTED ACTION
#
# TCP transports dictionaries.
# ActionDispatcher works with the generic Action
# model.
# --------------------------------------------------

running_action = Action.from_dict(
    consume_response["action"]
)


assert (
    running_action.action_id
    == action.action_id
)

assert (
    running_action.action
    == "sense_timber"
)


# --------------------------------------------------
# DISPATCH TO LOCAL SENSING HANDLER
# --------------------------------------------------

result = dispatcher.dispatch(
    running_action
)


print()
print(
    "[dispatcher] result:",
    result,
)


assert executed_action is not None

assert (
    executed_action.action_id
    == action.action_id
)

assert (
    result["equipment"]
    == "webcam"
)

assert (
    result["result"]
    == "timber_sensed"
)


# --------------------------------------------------
# REPORT SUCCESS THROUGH LOCAL AGENT
#
# execution endpoint
#       ↓ TCP
# sensing agent
#       ↓
# local terminal first
#       ↓
# master terminal
# --------------------------------------------------

terminal_response = execution_client.send(
    {
        "command": "mark_terminal",
        "action_status": "completed",
    }
)


print()
print(
    "[executor] terminal response:",
    terminal_response,
)


assert (
    terminal_response["status"]
    == "ok"
)

assert (
    terminal_response["action"]["status"]
    == ActionStatus.COMPLETED.value
)


# --------------------------------------------------
# VERIFY MASTER TERMINAL STATE
# --------------------------------------------------

master_completed = master_store.load(
    action.action_id
)


assert (
    master_completed.status
    == ActionStatus.COMPLETED
)

assert (
    master_completed.claimed_by
    == agent.agent_id
)


print()
print(
    "[master] completed:",
    master_completed.to_dict(),
)


# --------------------------------------------------
# VERIFY LOCAL TERMINAL SYNCHRONIZATION
# --------------------------------------------------

local_completed = agent_store.load(
    action.action_id
)


assert (
    local_completed["local_status"]
    == ActionStatus.COMPLETED.value
)

assert (
    local_completed["terminal_reported"]
    is True
)


print()
print(
    "[agent-store] completed:",
    local_completed,
)


# --------------------------------------------------
# COMPLETED ACTION MUST NO LONGER BE ACTIVE
# --------------------------------------------------

assert (
    agent_store.find_active()
    is None
)


print()
print(
    "[PASS] completed action released locally"
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


assert not agent_thread.is_alive()
assert not master_thread.is_alive()


print()
print(
    "[test] Action dispatcher TCP integration passed"
)