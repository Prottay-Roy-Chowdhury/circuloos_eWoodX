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
    WorkflowClient,
    WorkflowHandler,
)


# --------------------------------------------------
# TEST CONFIG
# --------------------------------------------------

HOST = "127.0.0.1"
MASTER_PORT = 5106

POLL_INTERVAL = 0.2


TEST_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "agent_poller_tcp"
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
#
# Avoid relying on one arbitrary sleep for
# background-thread behavior.
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


# Allow listening socket to start.
time.sleep(
    0.3
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


master_client = TCPClient(
    host=HOST,
    port=MASTER_PORT,
)


workflow_client = WorkflowClient(
    tcp_client=master_client,
    agent=agent,
    local_store=agent_store,
)


poller = AgentPoller(
    workflow_client=workflow_client,
    local_store=agent_store,
    interval=POLL_INTERVAL,
)


# ==================================================
# ACTION 1
# ==================================================

action_1 = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": (
            "scan_background_001"
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


assert (
    action_1.status
    == ActionStatus.PENDING
)


# --------------------------------------------------
# START BACKGROUND POLLER
# --------------------------------------------------

started = poller.start()


print(
    "[poller] first start:",
    started
)


assert started is True


# --------------------------------------------------
# DUPLICATE START MUST BE BLOCKED
# --------------------------------------------------

started_again = poller.start()


print(
    "[poller] second start:",
    started_again
)


assert started_again is False


# --------------------------------------------------
# WAIT FOR AUTOMATIC CLAIM
#
# No manual poll_once() call appears here.
# --------------------------------------------------

claimed_automatically = wait_until(
    lambda: (
        master_store.load(
            action_1.action_id
        ).status
        == ActionStatus.CLAIMED
    )
)


assert claimed_automatically is True


master_action_1 = master_store.load(
    action_1.action_id
)


print(
    "[master] action 1 automatically claimed:",
    master_action_1.to_dict()
)


assert (
    master_action_1.claimed_by
    == agent.agent_id
)


# --------------------------------------------------
# VERIFY LOCAL PERSISTENCE
# --------------------------------------------------

assert agent_store.exists(
    action_1.action_id
)


local_action_1 = agent_store.load(
    action_1.action_id
)


print(
    "[agent-store] action 1:",
    local_action_1
)


assert (
    local_action_1["action"]["action_id"]
    == action_1.action_id
)

assert (
    local_action_1["consumed"]
    is False
)


# ==================================================
# ACTION 2
#
# While action 1 is active locally, create another
# eligible pending action.
# ==================================================

action_2 = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": (
            "scan_background_002"
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


# --------------------------------------------------
# LET MULTIPLE POLLING CYCLES PASS
#
# The background poller is still running, but must
# not claim action 2 because action 1 is active.
# --------------------------------------------------

time.sleep(
    POLL_INTERVAL * 4
)


master_action_2 = master_store.load(
    action_2.action_id
)


print(
    "[master] action 2 after repeated polling:",
    master_action_2.to_dict()
)


assert (
    master_action_2.status
    == ActionStatus.PENDING
)


# --------------------------------------------------
# VERIFY ONLY ACTION 1 IS ACTIVE LOCALLY
# --------------------------------------------------

active_local = agent_store.find_active()


assert active_local is not None

assert (
    active_local["action"]["action_id"]
    == action_1.action_id
)


print(
    "[poller] active local guard preserved"
)


# --------------------------------------------------
# STOP POLLER
# --------------------------------------------------

stopped = poller.stop()


print()
print(
    "[poller] first stop:",
    stopped
)


assert stopped is True


# --------------------------------------------------
# SECOND STOP
#
# Already stopped -> should return False.
# --------------------------------------------------

stopped_again = poller.stop()


print(
    "[poller] second stop:",
    stopped_again
)


assert stopped_again is False


# --------------------------------------------------
# VERIFY BACKGROUND THREAD REALLY STOPPED
#
# TEST-ONLY:
# Remove action 1 locally so the agent would be free
# to claim action 2 if the poller were still running.
# --------------------------------------------------

deleted = agent_store.delete(
    action_1.action_id
)


assert deleted is True

assert (
    agent_store.find_active()
    is None
)


print(
    "[test-only] cleared local action 1"
)


# Give more than several poll intervals.
time.sleep(
    POLL_INTERVAL * 4
)


master_action_2_after_stop = (
    master_store.load(
        action_2.action_id
    )
)


print(
    "[master] action 2 after poller stopped:",
    master_action_2_after_stop.to_dict()
)


# If the background thread were still alive,
# action 2 would now have been claimed.
assert (
    master_action_2_after_stop.status
    == ActionStatus.PENDING
)


# --------------------------------------------------
# STOP MASTER TCP SERVER
# --------------------------------------------------

master_server.stop()


master_thread.join(
    timeout=2.0
)


assert not master_thread.is_alive()


print()
print(
    "[test] Background agent poller TCP passed"
)