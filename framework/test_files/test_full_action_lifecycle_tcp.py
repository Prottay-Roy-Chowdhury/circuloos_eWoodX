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
    action_1.to_dict(),
)


# ==================================================
# START BACKGROUND POLLER
# ==================================================

assert poller.start() is True


# ==================================================
# ACTION 1 AUTOMATIC CLAIM
# ==================================================

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


print()
print(
    "[master] action 1 claimed:",
    master_action_1.to_dict(),
)

print(
    "[agent-store] action 1 claimed:",
    local_action_1,
)


assert (
    master_action_1.status
    == ActionStatus.CLAIMED
)

assert (
    master_action_1.claimed_by
    == agent.agent_id
)

assert (
    local_action_1["local_status"]
    == "claimed"
)

assert (
    local_action_1["consumed"]
    is False
)

assert (
    local_action_1["terminal_reported"]
    is False
)


# ==================================================
# PREMATURE TERMINAL REQUEST
#
# The action has only been claimed.
#
# A terminal outcome belongs to executed work, so a
# claimed action cannot become terminal.
#
# The request must fail without changing either the
# master or local lifecycle state.
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
    premature_terminal,
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
    local_after_premature["terminal_reported"]
    is False
)

assert (
    agent_store.find_active()
    is not None
)


print(
    "[test] premature completion did not "
    "change or release action 1"
)


# ==================================================
# ACTION 2
#
# Create another eligible action while action 1 is
# still active.
#
# The agent must not claim it yet.
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
    action_2.to_dict(),
)


# Let several background poll cycles happen.
time.sleep(
    POLL_INTERVAL * 3
)


master_action_2_pending = (
    master_store.load(
        action_2.action_id
    )
)


assert (
    master_action_2_pending.status
    == ActionStatus.PENDING
)

assert (
    master_action_2_pending.claimed_by
    is None
)


print(
    "[master] action 2 remains pending "
    "while action 1 is active"
)


# ==================================================
# GRASSHOPPER CONSUMES ACTION 1
#
# Expected workflow:
#
# GH
#   ↓ consume_action
# agent marks consumed locally
#   ↓
# agent reports running to master
#   ↓
# master CLAIMED -> RUNNING
#   ↓ acknowledgement
# agent local CONSUMED -> RUNNING
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

assert (
    local_running["terminal_reported"]
    is False
)


print(
    "[master] action 1 running:",
    master_running.to_dict(),
)

print(
    "[agent-store] action 1 running:",
    local_running,
)


# --------------------------------------------------
# REPEATED CONSUME MUST NOT RETRIGGER ACTION 1
# --------------------------------------------------

second_consume_response = (
    grasshopper_client.send(
        {
            "command": "consume_action",
        }
    )
)


assert (
    second_consume_response["status"]
    == "ok"
)

assert (
    second_consume_response["trigger"]
    is False
)

assert (
    second_consume_response["action"]
    is None
)


print(
    "[test] repeated consume did not "
    "retrigger action 1"
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
# Execution ownership rule:
#
# The agent is the executor of this action.
#
# Therefore:
#
# 1. agent records COMPLETED locally first
#       terminal_reported=False
#
# 2. agent reports COMPLETED to master
#
# 3. master RUNNING -> COMPLETED
#
# 4. master acknowledgement is received
#
# 5. agent sets terminal_reported=True
#
# Only after step 5 is the local action released.
#
# The intermediate terminal_reported=False state is
# tested explicitly in test_terminal_sync.py.
# This real-TCP integration test verifies the complete
# successful transaction.
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
    terminal_response,
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
# VERIFY LOCAL TERMINAL AND SYNCHRONIZED
# --------------------------------------------------

local_completed = agent_store.load(
    action_1.action_id
)


assert (
    local_completed["local_status"]
    == "completed"
)

assert (
    local_completed["consumed"]
    is True
)

assert (
    local_completed["terminal_reported"]
    is True
)


print(
    "[master] action 1 completed:",
    master_completed.to_dict(),
)

print(
    "[agent-store] action 1 completed "
    "and synchronized:",
    local_completed,
)


# ==================================================
# ACTION 1 MUST NOW BE LOCALLY INACTIVE
#
# Terminal alone does not release an action.
#
# The release condition is:
#
# terminal status
# +
# terminal_reported=True
# ==================================================

active_after_completion = (
    agent_store.find_active()
)


# At this exact instant the poller may already have
# claimed action 2. Therefore:
#
# - None is valid if it has not claimed yet.
# - action 2 is valid if it has already claimed it.
# - action 1 must NEVER be returned again.

if active_after_completion is not None:
    assert (
        active_after_completion[
            "action"
        ][
            "action_id"
        ]
        != action_1.action_id
    )


print(
    "[test] synchronized terminal action 1 "
    "is no longer active"
)


# ==================================================
# CRITICAL AUTONOMOUS TRANSITION
#
# The background poller must now see that action 1
# has completed AND its terminal outcome has been
# acknowledged.
#
# Therefore the agent is free and may automatically
# claim action 2.
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
    master_action_2.to_dict(),
)

print(
    "[agent-store] action 2:",
    local_action_2,
)


assert (
    master_action_2.status
    == ActionStatus.CLAIMED
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

assert (
    local_action_2["terminal_reported"]
    is False
)


# ==================================================
# TERMINAL ACTION 1 MUST STILL EXIST
#
# Terminal history is retained locally.
#
# It is ignored by find_active() because its terminal
# outcome has already been synchronized.
# ==================================================

assert agent_store.exists(
    action_1.action_id
)

stored_action_1 = agent_store.load(
    action_1.action_id
)


assert (
    stored_action_1["local_status"]
    == "completed"
)

assert (
    stored_action_1["terminal_reported"]
    is True
)


# ==================================================
# find_active() MUST SELECT ACTION 2
# ==================================================

active_local = (
    agent_store.find_active()
)


assert active_local is not None

assert (
    active_local[
        "action"
    ][
        "action_id"
    ]
    == action_2.action_id
)


print(
    "[poller] synchronized terminal action 1 "
    "ignored; action 2 is now active"
)


# ==================================================
# MASTER FINAL STATE
# ==================================================

assert (
    master_store.load(
        action_1.action_id
    ).status
    == ActionStatus.COMPLETED
)

assert (
    master_store.load(
        action_2.action_id
    ).status
    == ActionStatus.CLAIMED
)


print()
print(
    "[master] final state:"
)

print(
    "  action 1 =",
    master_store.load(
        action_1.action_id
    ).status.value,
)

print(
    "  action 2 =",
    master_store.load(
        action_2.action_id
    ).status.value,
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