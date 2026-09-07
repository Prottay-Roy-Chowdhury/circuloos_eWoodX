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
# TEST CONFIG
# --------------------------------------------------

TEST_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "terminal_sync"
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


# ==================================================
# TEST-ONLY DIRECT TRANSPORT
# ==================================================

class FlakyDirectTCPClient(TCPClient):
    """
    Test-only transport.

    Requests are sent directly to WorkflowHandler.handle()
    without sockets.

    The first mark_terminal request is delivered to the
    master successfully, but the response is deliberately
    lost by raising ConnectionError afterward.
    """

    def __init__(
        self,
        handler,
    ):
        self.handler = handler
        self.fail_terminal_response_once = True

    def send(
        self,
        message,
    ):
        response = self.handler(
            message
        )

        if (
            message.get("command")
            == "mark_terminal"
            and self.fail_terminal_response_once
        ):
            self.fail_terminal_response_once = False

            raise ConnectionError(
                "Simulated lost terminal response."
            )

        return response


# ==================================================
# MASTER
# ==================================================

master_store = ActionStore(
    root=MASTER_ROOT
)

master_handler = WorkflowHandler(
    action_store=master_store
)


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


direct_client = FlakyDirectTCPClient(
    handler=master_handler.handle
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
        "source_artifact_id": (
            "scan_terminal_sync_001"
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


# --------------------------------------------------
# CLAIM ACTION 1
# --------------------------------------------------

claimed_action_1 = master_store.claim(
    action_id=action_1.action_id,
    agent=agent,
)

agent_store.save(
    claimed_action_1
)


print(
    "[master] action 1 claimed:",
    claimed_action_1.to_dict(),
)

print(
    "[agent-store] action 1 claimed:",
    agent_store.load(
        action_1.action_id
    ),
)


# --------------------------------------------------
# MOVE ACTION 1 TO RUNNING
#
# We establish the normal precondition directly.
# The running workflow itself has already been tested
# separately.
# --------------------------------------------------

agent_store.mark_consumed(
    action_1.action_id
)

master_store.mark_running(
    action_id=action_1.action_id,
    agent=agent,
)

agent_store.mark_running_reported(
    action_1.action_id
)


master_running = master_store.load(
    action_1.action_id
)

local_running = agent_store.load(
    action_1.action_id
)


assert (
    master_running.status
    == ActionStatus.RUNNING
)

assert (
    local_running["local_status"]
    == "running"
)

assert (
    local_running["consumed"]
    is True
)


print()
print(
    "[master] action 1 running:",
    master_running.to_dict(),
)

print(
    "[agent-store] action 1 running:",
    local_running,
)


# ==================================================
# ACTION 2
#
# This action must remain pending until action 1's
# terminal state has been synchronized successfully.
# ==================================================

action_2 = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": (
            "scan_terminal_sync_002"
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


# ==================================================
# FIRST TERMINAL REPORT
#
# Expected sequence:
#
# local RUNNING
#      ↓
# local COMPLETED
# terminal_reported=False
#      ↓
# master COMPLETED
#      ↓
# response is lost
#
# Therefore the request returns error locally even
# though the master transition succeeded.
# ==================================================

first_terminal_response = (
    agent_handler.handle(
        {
            "command": "mark_terminal",
            "action_status": "completed",
        }
    )
)


print()
print(
    "[agent] first terminal response:",
    first_terminal_response,
)


assert (
    first_terminal_response["status"]
    == "error"
)


# --------------------------------------------------
# MASTER DID RECEIVE COMPLETION
# --------------------------------------------------

master_after_lost_response = (
    master_store.load(
        action_1.action_id
    )
)


assert (
    master_after_lost_response.status
    == ActionStatus.COMPLETED
)


print(
    "[master] action 1 after lost response:",
    master_after_lost_response.to_dict(),
)


# --------------------------------------------------
# LOCAL EXECUTOR ALSO RECORDED COMPLETION
#
# But synchronization has NOT been acknowledged.
# --------------------------------------------------

local_after_lost_response = (
    agent_store.load(
        action_1.action_id
    )
)


assert (
    local_after_lost_response["local_status"]
    == "completed"
)

assert (
    local_after_lost_response[
        "terminal_reported"
    ]
    is False
)


print(
    "[agent-store] action 1 after lost response:",
    local_after_lost_response,
)


# ==================================================
# CRITICAL INVARIANT
#
# completed + terminal_reported=False
# MUST STILL BE ACTIVE.
# ==================================================

active_after_failure = (
    agent_store.find_active()
)


assert active_after_failure is not None

assert (
    active_after_failure[
        "action"
    ][
        "action_id"
    ]
    == action_1.action_id
)


print(
    "[test] terminal-but-unreported action "
    "remains active"
)


# --------------------------------------------------
# POLLER MUST NOT CLAIM ACTION 2
# --------------------------------------------------

poll_result = poller.poll_once()


assert poll_result is not None

assert (
    poll_result[
        "action"
    ][
        "action_id"
    ]
    == action_1.action_id
)


master_action_2_before_retry = (
    master_store.load(
        action_2.action_id
    )
)


assert (
    master_action_2_before_retry.status
    == ActionStatus.PENDING
)

assert (
    master_action_2_before_retry.claimed_by
    is None
)


print(
    "[test] action 2 remains pending while "
    "terminal report is unacknowledged"
)


# ==================================================
# RETRY THE SAME TERMINAL REPORT
#
# Local mark_terminal() must be idempotent.
#
# Master mark_terminal() must also accept:
#
# COMPLETED → COMPLETED
#
# for the same owning agent.
# ==================================================

second_terminal_response = (
    agent_handler.handle(
        {
            "command": "mark_terminal",
            "action_status": "completed",
        }
    )
)


print()
print(
    "[agent] second terminal response:",
    second_terminal_response,
)


assert (
    second_terminal_response["status"]
    == "ok"
)


# --------------------------------------------------
# VERIFY MASTER STILL COMPLETED
# --------------------------------------------------

master_after_retry = (
    master_store.load(
        action_1.action_id
    )
)


assert (
    master_after_retry.status
    == ActionStatus.COMPLETED
)


# --------------------------------------------------
# VERIFY LOCAL SYNCHRONIZATION ACKNOWLEDGED
# --------------------------------------------------

local_after_retry = (
    agent_store.load(
        action_1.action_id
    )
)


assert (
    local_after_retry["local_status"]
    == "completed"
)

assert (
    local_after_retry[
        "terminal_reported"
    ]
    is True
)


print(
    "[agent-store] action 1 synchronized:",
    local_after_retry,
)


# ==================================================
# ACTION 1 MUST NOW BE INACTIVE
# ==================================================

assert (
    agent_store.find_active()
    is None
)


print(
    "[test] synchronized terminal action "
    "released the agent"
)


# ==================================================
# POLLER MAY NOW CLAIM ACTION 2
# ==================================================

poll_result_2 = poller.poll_once()


assert poll_result_2 is not None


master_action_2_after_retry = (
    master_store.load(
        action_2.action_id
    )
)

local_action_2 = agent_store.load(
    action_2.action_id
)


assert (
    master_action_2_after_retry.status
    == ActionStatus.CLAIMED
)

assert (
    master_action_2_after_retry.claimed_by
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
    local_action_2[
        "terminal_reported"
    ]
    is False
)


print()
print(
    "[master] action 2 claimed:",
    master_action_2_after_retry.to_dict(),
)

print(
    "[agent-store] action 2:",
    local_action_2,
)


# ==================================================
# FINAL
# ==================================================

print()
print(
    "[test] Terminal synchronization lifecycle passed"
)