from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.communication.core import (
    Action,
)

from framework.communication.transport import (
    TCPClient,
)

from framework.orchestration import (
    ActionDispatcher,
)

from projects.ewoodx.config import (
    SENSING_AGENT_HOST,
    SENSING_AGENT_PORT,
)

from projects.ewoodx.entrypoints.sensing_entrypoint import (
    EWoodXSensingEntrypoint,
)


def run_sense_timber(
    action: Action,
) -> None:
    """
    Execute the eWoodX timber sensing process.
    """

    print()
    print(
        "[eWoodX] Executing distributed action:"
    )

    print(
        f"[eWoodX] Action ID: {action.action_id}"
    )

    print(
        f"[eWoodX] Action: {action.action}"
    )

    entrypoint = EWoodXSensingEntrypoint()

    entrypoint.run()


def main() -> None:
    """
    Consume and execute one action from the local
    eWoodX sensing agent.
    """

    client = TCPClient(
        host=SENSING_AGENT_HOST,
        port=SENSING_AGENT_PORT,
    )

    dispatcher = ActionDispatcher()

    dispatcher.register(
        action="sense_timber",
        handler=run_sense_timber,
    )

    # ---------------------------------------------------------
    # Consume local action
    # ---------------------------------------------------------

    response = client.send(
        {
            "command": "consume_action",
        }
    )

    if response.get("status") != "ok":
        raise RuntimeError(
            response.get(
                "message",
                "Failed to consume action.",
            )
        )

    if response.get("trigger") is not True:

        print()
        print(
            "[eWoodX] No sensing action available."
        )

        return

    action_data = response.get(
        "action"
    )

    if not isinstance(
        action_data,
        dict,
    ):
        raise ValueError(
            "Invalid action response."
        )

    action = Action.from_dict(
        action_data
    )

    # ---------------------------------------------------------
    # Execute
    # ---------------------------------------------------------

    try:

        dispatcher.dispatch(
            action
        )

    except Exception as execution_error:

        terminal_response = client.send(
            {
                "command": "mark_terminal",
                "action_status": "failed",
            }
        )

        if (
            terminal_response.get("status")
            != "ok"
        ):
            print()
            print(
                "[eWoodX] Failed to report "
                "terminal failure:"
            )
            print(
                terminal_response
            )

        raise execution_error

    terminal_response = client.send(
        {
            "command": "mark_terminal",
            "action_status": "completed",
        }
    )

    if (
        terminal_response.get("status")
        != "ok"
    ):
        raise RuntimeError(
            terminal_response.get(
                "message",
                "Failed to report completion.",
            )
        )


if __name__ == "__main__":
    main()