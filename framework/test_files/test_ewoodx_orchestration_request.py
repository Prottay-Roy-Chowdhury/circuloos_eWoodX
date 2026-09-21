from pathlib import Path
import sys
import time


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.communication.transport import (
    TCPClient,
)

from framework.workspace import (
    load_workspace,
)

from projects.ewoodx.config import (
    AGENTS_RUNTIME_DIRECTORY,
    EWOODX_REPOSITORY_ROOT,
    SENSING_AGENT_HOST,
    SENSING_AGENT_ID,
    SENSING_AGENT_PORT,
)


CLAIM_TIMEOUT = 5.0
CHECK_INTERVAL = 0.1


def main() -> None:

    # ---------------------------------------------------------
    # Local sensing-agent connection
    # ---------------------------------------------------------

    client = TCPClient(
        host=SENSING_AGENT_HOST,
        port=SENSING_AGENT_PORT,
    )

    # ---------------------------------------------------------
    # Request orchestration through the sensing agent
    # ---------------------------------------------------------

    response = client.send(
        {
            "command": "start_orchestration",
            "orchestration": "sensing",
        }
    )

    print()
    print("[test] Local request response:")
    print(response)

    assert response.get("status") == "ok"

    assert (
        response.get("orchestration")
        == "sensing"
    )

    action = response.get("action")

    assert isinstance(
        action,
        dict,
    )

    action_id = action.get(
        "action_id"
    )

    assert action_id

    # ---------------------------------------------------------
    # Verify initial orchestration result
    # ---------------------------------------------------------

    assert (
        action.get("action")
        == "sense_timber"
    )

    assert (
        action.get("target")
        == "sensing"
    )

    assert (
        action.get("status")
        == "pending"
    )

    assert (
        action.get("claimed_by")
        is None
    )

    metadata = action.get(
        "metadata"
    )

    assert isinstance(
        metadata,
        dict,
    )

    assert (
        metadata.get("orchestration_name")
        == "sensing"
    )

    assert (
        metadata.get("orchestration_step_id")
        == "sense_timber"
    )

    assert (
        metadata.get("orchestration_step_index")
        == 0
    )

    assert metadata.get(
        "orchestration_id"
    )

    print()
    print(
        "[test] Orchestration request reached "
        "the master successfully."
    )

    print(
        f"[test] Action ID: {action_id}"
    )

    # ---------------------------------------------------------
    # Resolve current workspace runtime paths
    # ---------------------------------------------------------

    workspace = load_workspace(
        project_root=EWOODX_REPOSITORY_ROOT,
    )

    master_action_path = (
        workspace.root
        / AGENTS_RUNTIME_DIRECTORY
        / "master"
        / f"{action_id}.json"
    )

    sensing_action_path = (
        workspace.root
        / AGENTS_RUNTIME_DIRECTORY
        / SENSING_AGENT_ID
        / f"{action_id}.json"
    )

    # ---------------------------------------------------------
    # Wait for AgentPoller to claim and persist the action
    # ---------------------------------------------------------

    deadline = (
        time.monotonic()
        + CLAIM_TIMEOUT
    )

    while time.monotonic() < deadline:

        if (
            master_action_path.is_file()
            and sensing_action_path.is_file()
        ):
            break

        time.sleep(
            CHECK_INTERVAL
        )

    assert master_action_path.is_file(), (
        "Master action was not found."
    )

    assert sensing_action_path.is_file(), (
        "Sensing agent did not claim and "
        "persist the action within the timeout."
    )

    # ---------------------------------------------------------
    # Read persisted states
    # ---------------------------------------------------------

    import json

    with master_action_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        master_action = json.load(
            file
        )

    with sensing_action_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        sensing_action = json.load(
            file
        )

    print()
    print("[test] Master persisted action:")
    print(master_action)

    print()
    print("[test] Sensing persisted action:")
    print(sensing_action)

    # ---------------------------------------------------------
    # Verify authoritative master claim
    # ---------------------------------------------------------

    assert (
        master_action.get("action_id")
        == action_id
    )

    assert (
        master_action.get("status")
        == "claimed"
    )

    assert (
        master_action.get("claimed_by")
        == SENSING_AGENT_ID
    )

    # ---------------------------------------------------------
    # Verify agent-local durable state
    # ---------------------------------------------------------

    assert (
        sensing_action.get("agent_id")
        == SENSING_AGENT_ID
    )

    local_action = sensing_action.get(
        "action"
    )

    assert isinstance(
        local_action,
        dict,
    )

    assert (
        local_action.get("action_id")
        == action_id
    )

    assert (
        local_action.get("status")
        == "claimed"
    )

    assert (
        local_action.get("claimed_by")
        == SENSING_AGENT_ID
    )

    assert (
        sensing_action.get("local_status")
        == "claimed"
    )

    assert (
        sensing_action.get("consumed")
        is False
    )

    assert (
        sensing_action.get("terminal_reported")
        is False
    )

    print()
    print(
        "[PASS] Complete eWoodX orchestration "
        "request and claim path verified."
    )

    print()
    print(
        "local client"
        " -> sensing agent :6105"
        " -> master :5105"
        " -> orchestration"
        " -> pending action"
        " -> sensing poller"
        " -> claimed action"
        " -> local persistence"
    )


if __name__ == "__main__":
    main()