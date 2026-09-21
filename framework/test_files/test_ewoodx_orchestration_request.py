from pathlib import Path
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

from projects.ewoodx.config import (
    MASTER_HOST,
    MASTER_PORT,
)


def main() -> None:

    client = TCPClient(
        host=MASTER_HOST,
        port=MASTER_PORT,
    )

    response = client.send(
        {
            "command": "start_orchestration",
            "orchestration": "sensing",
        }
    )

    print()
    print("[test] Response:")
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
        "metadata",
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
        "[PASS] eWoodX sensing orchestration "
        "request created a pending action."
    )


if __name__ == "__main__":
    main()