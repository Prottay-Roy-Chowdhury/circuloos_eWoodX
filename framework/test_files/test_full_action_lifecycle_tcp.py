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
    AgentPoller,
    AgentWorkflowHandler,
    WorkflowClient,
    WorkflowHandler,
)


# --------------------------------------------------
# TEST CONFIG
# --------------------------------------------------

HOST = "127.0.0.1"

MASTER_PORT = 5107
AGENT_PORT = 6107

POLL_INTERVAL = 0.2


TEST_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "full_action_lifecycle_tcp"
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
# WAIT HELPER
# --------------------------------------------------

def wait_until(
    condition,
    timeout=3.0,
    interval=0.05,
):
    deadline = (
        time.time()
        + timeout
    )

    while time.time() < deadline:
        if condition():
            return True

        time.sleep(
            interval
        )

    return False


# ==================================================
# MASTER
# ==================================================

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


# ==================================================
# AGENT
# ==================================================

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


# Agent -> master
master_client = TCPClient(
    host=HOST,
    port=MASTER_PORT,
)

workflow_client = WorkflowClient(
    tcp_client=master_client,
    agent=agent,
    local_store=agent_store,
)


# Local GH-facing workflow handler
agent_handler = AgentWorkflowHandler(
    local_store=agent_store,
    workflow_client=workflow_client,
)


# Local agent TCP server
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


# Simulated Grasshopper -> agent
grasshopper_client = TCPClient(
    host=HOST,
    port=AGENT_PORT,
)


# Background poller
poller = AgentPoller(
    workflow_client=workflow_client,
    local_store=agent_store,
    interval=POLL_INTERVAL,
)


# Let both TCP servers begin listening.
time.sleep(
    0.3
)


# ==================================================
# ACTION 1
# ==================================================

action_1 = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": (
            "scan_lifecycle_001"
        ),
    },
)

master_store.save(
    action_1
)


print()
print(
    "[master] action 1 created:",
    action_1.to_dict()
)


# --------------------------------------------------
# START POLLER
# --------------------------------------------------

assert poller.start() is True


# --------------------------------------------------
# BACKGROUND CLAIM
# --------------------------------------------------

claimed_1 = wait_until(
    lambda: (
        master_store.load(
            action_1.action_id
        ).status
        == ActionStatus.CLAIMED
    )
)

assert claimed_1 is True


master_action_1 = master_store.load(
    action_1.action_id
)

local_action_1 = agent_store.load(
    action_1.action_id
)


print(
    "[master] action 1 claimed:",
    master_action_1.to_dict()
)

print(
    "[agent-store] action 1 claimed:",
    local_action_1
)


assert (
    local_action_1["local_status"]
    == "claimed"
)

assert (
    local_action_1["consumed"]
    is False
)


# ==================================================
# PREMATURE TERMINAL REQUEST
#
# Important failure-boundary test.
#
# Master action is only CLAIMED, not RUNNING.
# Completion must fail and local action must remain
# active/claimed.
# ==================================================

premature_terminal = (
    grasshopper_client.send(
        {
            "command": "mark_terminal",
            "action_status": "completed",
        }
    )
)


print()
print(
    "[grasshopper] premature terminal:",
    premature_terminal
)


assert (
    premature_terminal["status"]
    == "error"
)


master_after_premature = (
    master_store.load(
        action_1.action_id
    )
)

local_after_premature = (
    agent_store.load(
        action_1.action_id
    )
)


assert (
    master_after_premature.status
    == ActionStatus.CLAIMED
)

assert (
    local_after_premature["local_status"]
    == "claimed"
)

assert (
    agent_store.find_active()
    is not None
)


print(
    "[test] premature completion did not free agent"
)


# ==================================================
# ACTION 2
#
# Add it while action 1 remains active.
# ==================================================

action_2 = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": (
            "scan_lifecycle_002"
        ),
    },
)

master_store.save(
    action_2
)


print()
print(
    "[master] action 2 created:",
    action_2.to_dict()
)


# Let several poll cycles happen.
time.sleep(
    POLL_INTERVAL * 3
)


assert (
    master_store.load(
        action_2.action_id
    ).status
    == ActionStatus.PENDING
)


print(
    "[master] action 2 remains pending "
    "while action 1 is active"
)


# ==================================================
# GRASSHOPPER CONSUMES ACTION 1
# ==================================================

consume_response = (
    grasshopper_client.send(
        {
            "command": "consume_action",
        }
    )
)


print()
print(
    "[grasshopper] consume action 1:",
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


# --------------------------------------------------
# VERIFY MASTER RUNNING
# --------------------------------------------------

master_running = master_store.load(
    action_1.action_id
)


assert (
    master_running.status
    == ActionStatus.RUNNING
)


# --------------------------------------------------
# VERIFY LOCAL RUNNING
# --------------------------------------------------

local_running = agent_store.load(
    action_1.action_id
)


assert (
    local_running["consumed"]
    is True
)

assert (
    local_running["local_status"]
    == "running"
)


print(
    "[master] action 1 running:",
    master_running.to_dict()
)

print(
    "[agent-store] action 1 running:",
    local_running
)


# --------------------------------------------------
# ACTION 2 MUST STILL BE PENDING
# --------------------------------------------------

time.sleep(
    POLL_INTERVAL * 2
)


assert (
    master_store.load(
        action_2.action_id
    ).status
    == ActionStatus.PENDING
)


# ==================================================
# COMPLETE ACTION 1
#
# GH -> agent TCP
# agent -> master TCP
#
# Required ordering:
#
# master running -> completed
# local running  -> completed
# ==================================================

terminal_response = (
    grasshopper_client.send(
        {
            "command": "mark_terminal",
            "action_status": "completed",
        }
    )
)


print()
print(
    "[grasshopper] complete action 1:",
    terminal_response
)


assert (
    terminal_response["status"]
    == "ok"
)


# --------------------------------------------------
# VERIFY MASTER TERMINAL
# --------------------------------------------------

master_completed = master_store.load(
    action_1.action_id
)


assert (
    master_completed.status
    == ActionStatus.COMPLETED
)


# --------------------------------------------------
# VERIFY LOCAL TERMINAL
# --------------------------------------------------

local_completed = agent_store.load(
    action_1.action_id
)


assert (
    local_completed["local_status"]
    == "completed"
)


print(
    "[master] action 1 completed:",
    master_completed.to_dict()
)

print(
    "[agent-store] action 1 completed:",
    local_completed
)


# ==================================================
# CRITICAL AUTONOMOUS TRANSITION
#
# The poller should now see:
#
# action 1 = terminal locally
#           -> not active
#
# then automatically claim action 2.
# ==================================================

action_2_claimed = wait_until(
    lambda: (
        master_store.load(
            action_2.action_id
        ).status
        == ActionStatus.CLAIMED
    ),
    timeout=4.0,
)


assert action_2_claimed is True


master_action_2 = master_store.load(
    action_2.action_id
)

local_action_2 = agent_store.load(
    action_2.action_id
)


print()
print(
    "[master] action 2 automatically claimed:",
    master_action_2.to_dict()
)

print(
    "[agent-store] action 2:",
    local_action_2
)


assert (
    master_action_2.claimed_by
    == agent.agent_id
)

assert (
    local_action_2["local_status"]
    == "claimed"
)

assert (
    local_action_2["consumed"]
    is False
)


# --------------------------------------------------
# TERMINAL ACTION 1 MUST STILL EXIST
#
# We retain local terminal history rather than
# deleting it.
# --------------------------------------------------

assert agent_store.exists(
    action_1.action_id
)

assert (
    agent_store.load(
        action_1.action_id
    )["local_status"]
    == "completed"
)


# --------------------------------------------------
# find_active() MUST NOW SELECT ACTION 2
# --------------------------------------------------

active_local = (
    agent_store.find_active()
)


assert active_local is not None

assert (
    active_local["action"]["action_id"]
    == action_2.action_id
)


print(
    "[poller] terminal action 1 ignored; "
    "action 2 is now active"
)


# ==================================================
# CLEANUP
# ==================================================

assert poller.stop() is True


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
    "[test] Full autonomous action lifecycle TCP passed"
)