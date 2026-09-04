from framework.communication.core import (
    Action,
    ActionStatus,
    Agent,
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