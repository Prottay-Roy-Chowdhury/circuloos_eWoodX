from pathlib import Path
import sys
import shutil


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

# --------------------------------------------------
# AGENT LOCAL ACTION STORE TEST
# --------------------------------------------------

agent_store = AgentActionStore(
    root=(
        PROJECT_ROOT
        / "test_file_transfer_data"
        / "test_data"
        / "agent_actions"
    ),
    agent=agent,
)


local_path = agent_store.save(
    claimed_action
)


print(
    "[agent-store] saved:",
    local_path
)


assert agent_store.exists(
    claimed_action.action_id
)

assert not agent_store.is_consumed(
    claimed_action.action_id
)


consumed_data = (
    agent_store.mark_consumed(
        claimed_action.action_id
    )
)


print(
    "[agent-store] consumed:",
    consumed_data
)


assert agent_store.is_consumed(
    claimed_action.action_id
)


print(
    "[test] AgentActionStore passed"
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

# --------------------------------------------------
# ACTION DISCOVERY TEST
# --------------------------------------------------

discovery_root = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "discovery_actions"
)


shutil.rmtree(
    discovery_root,
    ignore_errors=True,
)


discovery_store = ActionStore(
    root=discovery_root
)

design_action = Action(
    action="generate_design",
    target="design",
    payload={
        "source_artifact_id": "scan_002",
    },
)


preview_action = Action(
    action="generate_preview",
    target="preview",
    payload={
        "source_artifact_id": "design_001",
    },
)


robot_action = Action(
    action="execute_robot",
    target="robot",
    payload={
        "source_artifact_id": "toolpath_001",
    },
)

discovery_store.save(
    design_action
)

discovery_store.save(
    preview_action
)

discovery_store.save(
    robot_action
)

all_actions = (
    discovery_store.list_actions()
)


print(
    "[discovery] all actions:",
    [
        item.action
        for item in all_actions
    ]
)


assert len(
    all_actions
) == 3

design_pending = (
    discovery_store.find_pending(
        targets=agent.roles
    )
)


print(
    "[discovery] design agent:",
    [
        {
            "action": item.action,
            "target": item.target,
        }
        for item in design_pending
    ]
)

assert len(
    design_pending
) == 2


assert {
    item.target
    for item in design_pending
} == {
    "design",
    "preview",
}

robot_agent = Agent(
    agent_id="robot_pc_01",
    roles=[
        "robot",
    ],
)

robot_pending = (
    discovery_store.find_pending(
        targets=robot_agent.roles
    )
)


print(
    "[discovery] robot agent:",
    [
        {
            "action": item.action,
            "target": item.target,
        }
        for item in robot_pending
    ]
)


assert len(
    robot_pending
) == 1

assert (
    robot_pending[0].target
    == "robot"
)

print(
    "[test] Action discovery passed"
)