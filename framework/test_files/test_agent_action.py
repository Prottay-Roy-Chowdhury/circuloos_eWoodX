from pathlib import Path
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
)

# --------------------------------------------------
# ACTION TEST
# --------------------------------------------------

action = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": "scan_001",
    },
)


print(
    action.to_dict()
)


assert (
    action.status
    == ActionStatus.PENDING
)

assert (
    action.target
    == "design"
)


restored_action = Action.from_dict(
    action.to_dict()
)


assert (
    restored_action.action_id
    == action.action_id
)

assert (
    restored_action.action
    == action.action
)

assert (
    restored_action.payload
    == action.payload
)


print(
    "[test] Action model passed"
)


# --------------------------------------------------
# AGENT TEST
# --------------------------------------------------

agent = Agent(
    agent_id="design_pc_01",
    roles=[
        "design",
        "preview",
    ],
)


print(
    agent.to_dict()
)


assert agent.has_role(
    "design"
)

assert agent.can_handle(
    action.target
)

assert not agent.can_handle(
    "robot"
)


restored_agent = Agent.from_dict(
    agent.to_dict()
)


assert (
    restored_agent.agent_id
    == agent.agent_id
)

assert (
    restored_agent.roles
    == agent.roles
)


print(
    "[test] Agent model passed"
)

# --------------------------------------------------
# ACTION STORE TEST
# --------------------------------------------------

test_store_root = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "actions"
)


store = ActionStore(
    root=test_store_root
)


stored_path = store.save(
    action
)


print(
    "[store] saved:",
    stored_path
)


assert store.exists(
    action.action_id
)


loaded_action = store.load(
    action.action_id
)


print(
    "[store] loaded:",
    loaded_action.to_dict()
)


assert (
    loaded_action.action_id
    == action.action_id
)

assert (
    loaded_action.action
    == action.action
)

assert (
    loaded_action.target
    == action.target
)

assert (
    loaded_action.payload
    == action.payload
)


print(
    "[test] ActionStore passed"
)

# --------------------------------------------------
# ACTION CLAIM TEST
# --------------------------------------------------

claimed_action = store.claim(
    action_id=action.action_id,
    agent=agent,
)


print(
    "[claim] action:",
    claimed_action.to_dict()
)


assert (
    claimed_action.status
    == ActionStatus.CLAIMED
)

assert (
    claimed_action.claimed_by
    == agent.agent_id
)


stored_claimed_action = store.load(
    action.action_id
)


assert (
    stored_claimed_action.status
    == ActionStatus.CLAIMED
)

assert (
    stored_claimed_action.claimed_by
    == agent.agent_id
)


print(
    "[test] Action claim passed"
)

running_action = store.mark_running(
    action_id=action.action_id,
    agent=agent,
)

print(
    "[running] action:",
    running_action.to_dict()
)

assert (
    running_action.status
    == ActionStatus.RUNNING
)


completed_action = store.mark_terminal(
    action_id=action.action_id,
    agent=agent,
    status=ActionStatus.COMPLETED,
)

print(
    "[completed] action:",
    completed_action.to_dict()
)

assert (
    completed_action.status
    == ActionStatus.COMPLETED
)

print(
    "[test] Action lifecycle passed"
)