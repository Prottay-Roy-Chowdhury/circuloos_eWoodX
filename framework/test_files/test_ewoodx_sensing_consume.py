from pathlib import Path
import json
import sys


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


def main() -> None:

    # ---------------------------------------------------------
    # Current workspace
    # ---------------------------------------------------------

    workspace = load_workspace(
        project_root=EWOODX_REPOSITORY_ROOT,
    )

    sensing_runtime_root = (
        workspace.root
        / AGENTS_RUNTIME_DIRECTORY
        / SENSING_AGENT_ID
    )

    master_runtime_root = (
        workspace.root
        / AGENTS_RUNTIME_DIRECTORY
        / "master"
    )

    # ---------------------------------------------------------
    # Find the current claimed sensing action
    # ---------------------------------------------------------

    local_action_files = sorted(
        sensing_runtime_root.glob("*.json")
    )

    assert local_action_files, (
        "No sensing-agent action exists. "
        "Run the orchestration request test first."
    )

    claimed_record = None

    for path in local_action_files:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

        if (
            data.get("local_status")
            == "claimed"
            and data.get("consumed")
            is False
        ):
            claimed_record = data
            break

    assert claimed_record is not None, (
        "No unconsumed claimed sensing action found."
    )

    action = claimed_record.get(
        "action"
    )

    assert isinstance(
        action,
        dict,
    )

    action_id = action.get(
        "action_id"
    )

    assert action_id

    print()
    print(
        f"[test] Claimed action: {action_id}"
    )

    # ---------------------------------------------------------
    # Connect through the sensing agent's local API
    # ---------------------------------------------------------

    client = TCPClient(
        host=SENSING_AGENT_HOST,
        port=SENSING_AGENT_PORT,
    )

    response = client.send(
        {
            "command": "consume_action",
        }
    )

    print()
    print("[test] Consume response:")
    print(response)

    # ---------------------------------------------------------
    # Verify response
    # ---------------------------------------------------------

    assert (
        response.get("status")
        == "ok"
    )

    assert (
        response.get("trigger")
        is True
    )

    response_action = response.get(
        "action"
    )

    assert isinstance(
        response_action,
        dict,
    )

    assert (
        response_action.get("action_id")
        == action_id
    )

    assert (
        response_action.get("action")
        == "sense_timber"
    )

    assert (
        response_action.get("status")
        == "running"
    )

    # ---------------------------------------------------------
    # Verify master authoritative state
    # ---------------------------------------------------------

    master_action_path = (
        master_runtime_root
        / f"{action_id}.json"
    )

    assert master_action_path.is_file()

    with master_action_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        master_action = json.load(
            file
        )

    print()
    print("[test] Master persisted action:")
    print(master_action)

    assert (
        master_action.get("status")
        == "running"
    )

    assert (
        master_action.get("claimed_by")
        == SENSING_AGENT_ID
    )

    # ---------------------------------------------------------
    # Verify sensing-local state
    # ---------------------------------------------------------

    sensing_action_path = (
        sensing_runtime_root
        / f"{action_id}.json"
    )

    with sensing_action_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        sensing_action = json.load(
            file
        )

    print()
    print("[test] Sensing persisted action:")
    print(sensing_action)

    assert (
        sensing_action.get("local_status")
        == "running"
    )

    assert (
        sensing_action.get("consumed")
        is True
    )

    assert (
        sensing_action.get("terminal_reported")
        is False
    )

    # ---------------------------------------------------------
    # Verify one-shot consume behavior
    # ---------------------------------------------------------

    second_response = client.send(
        {
            "command": "consume_action",
        }
    )

    print()
    print("[test] Second consume response:")
    print(second_response)

    assert (
        second_response.get("status")
        == "ok"
    )

    assert (
        second_response.get("trigger")
        is False
    )

    print()
    print(
        "[PASS] eWoodX sensing consume and "
        "running synchronization verified."
    )

    print()
    print(
        "claimed"
        " -> local :6105 consume"
        " -> local consumed"
        " -> master running"
        " -> local running"
        " -> second consume suppressed"
    )


if __name__ == "__main__":
    main()