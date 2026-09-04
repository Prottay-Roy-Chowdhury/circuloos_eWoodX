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
    AgentPoller,
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
    / "agent_poller"
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
#
# Keep this test focused on polling behavior.
# Real TCP is already tested separately.
# --------------------------------------------------

class DirectTCPClient(
    TCPClient
):
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


direct_client = DirectTCPClient(
    handler=master_handler
)


workflow_client = WorkflowClient(
    tcp_client=direct_client,
    agent=agent,
    local_store=agent_store,
)


agent_handler = AgentWorkflowHandler(
    local_store=agent_store,
    workflow_client=workflow_client,
)


poller = AgentPoller(
    workflow_client=workflow_client,
    local_store=agent_store,
    interval=1.0,
)


# ==================================================
# ACTION 1
# ==================================================

action_1 = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": "scan_001",
    },
)


master_store.save(
    action_1
)


print(
    "[master] action 1 created:",
    action_1.to_dict()
)


assert (
    action_1.status
    == ActionStatus.PENDING
)


# --------------------------------------------------
# POLL 1
#
# No local action exists.
# Poller should claim action 1.
# --------------------------------------------------

poll_1 = poller.poll_once()


print(
    "[poller] first poll:",
    poll_1
)


assert poll_1 is not None

assert (
    poll_1["action"]["action_id"]
    == action_1.action_id
)

assert (
    poll_1["consumed"]
    is False
)


master_action_1 = master_store.load(
    action_1.action_id
)


assert (
    master_action_1.status
    == ActionStatus.CLAIMED
)

assert (
    master_action_1.claimed_by
    == agent.agent_id
)


print(
    "[master] action 1 claimed:",
    master_action_1.to_dict()
)


# --------------------------------------------------
# POLL 2
#
# Active local action already exists.
#
# Poller must return the same local action and must
# not attempt another claim.
# --------------------------------------------------

poll_2 = poller.poll_once()


print(
    "[poller] second poll:",
    poll_2
)


assert poll_2 is not None

assert (
    poll_2["action"]["action_id"]
    == action_1.action_id
)

assert (
    poll_2["consumed"]
    is False
)


# ==================================================
# ACTION 2
#
# Add another eligible pending action while
# action 1 is still active locally.
# ==================================================

action_2 = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": "scan_002",
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


assert (
    action_2.status
    == ActionStatus.PENDING
)


# --------------------------------------------------
# POLL 3
#
# Action 1 is still active.
#
# Action 2 must remain pending.
# --------------------------------------------------

poll_3 = poller.poll_once()


print(
    "[poller] third poll:",
    poll_3
)


assert poll_3 is not None

assert (
    poll_3["action"]["action_id"]
    == action_1.action_id
)


master_action_2 = master_store.load(
    action_2.action_id
)


assert (
    master_action_2.status
    == ActionStatus.PENDING
)


print(
    "[master] action 2 remains pending:",
    master_action_2.to_dict()
)


# --------------------------------------------------
# CONSUME ACTION 1
#
# This changes:
#
# local:
#     consumed = True
#
# master:
#     claimed -> running
# --------------------------------------------------

consume_response = agent_handler.handle(
    {
        "command": "consume_action",
    }
)


print()
print(
    "[agent-handler] consume action 1:",
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

assert agent_store.is_consumed(
    action_1.action_id
)


master_action_1_running = (
    master_store.load(
        action_1.action_id
    )
)


assert (
    master_action_1_running.status
    == ActionStatus.RUNNING
)


print(
    "[master] action 1 running:",
    master_action_1_running.to_dict()
)


# --------------------------------------------------
# POLL 4
#
# CRITICAL DECO2 PARITY TEST
#
# Action 1 has been consumed by GH, but it is still
# an active local action.
#
# Therefore action 2 MUST NOT be claimed.
# --------------------------------------------------

poll_4 = poller.poll_once()


print()
print(
    "[poller] poll after consume:",
    poll_4
)


assert poll_4 is not None

assert (
    poll_4["action"]["action_id"]
    == action_1.action_id
)

assert (
    poll_4["consumed"]
    is True
)


master_action_2_after_consume = (
    master_store.load(
        action_2.action_id
    )
)


assert (
    master_action_2_after_consume.status
    == ActionStatus.PENDING
)


print(
    "[master] action 2 still pending:",
    master_action_2_after_consume.to_dict()
)


# --------------------------------------------------
# STORE-LEVEL PROTECTION
#
# Even if something bypasses the poller and tries
# to save another claimed action locally, the store
# must reject it.
# --------------------------------------------------

fake_second_claim = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": "scan_fake",
    },
)

fake_second_claim.status = (
    ActionStatus.CLAIMED
)

fake_second_claim.claimed_by = (
    agent.agent_id
)


store_blocked_second_action = False


try:
    agent_store.save(
        fake_second_claim
    )

except RuntimeError as error:
    store_blocked_second_action = True

    print()
    print(
        "[agent-store] second active action blocked:",
        error,
    )


assert (
    store_blocked_second_action
    is True
)


# --------------------------------------------------
# FINAL STATE
# --------------------------------------------------

assert (
    master_store.load(
        action_1.action_id
    ).status
    == ActionStatus.RUNNING
)

assert (
    master_store.load(
        action_2.action_id
    ).status
    == ActionStatus.PENDING
)


print()
print(
    "[test] Agent poller poll_once passed"
)