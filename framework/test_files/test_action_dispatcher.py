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
)

from framework.orchestration import (
    ActionDispatcher,
)


# ==================================================
# TEST HANDLER
# ==================================================

received_action = None


def handle_sensing(
    action: Action,
):
    global received_action

    received_action = action

    return {
        "status": "executed",
        "equipment": action.payload.get(
            "equipment"
        ),
    }


# ==================================================
# DISPATCHER
# ==================================================

dispatcher = ActionDispatcher()

dispatcher.register(
    action="sense_timber",
    handler=handle_sensing,
)


# ==================================================
# ACTION
# ==================================================

action = Action(
    action="sense_timber",
    target="sensing",
    payload={
        "equipment": "webcam",
    },
)


result = dispatcher.dispatch(
    action
)


# ==================================================
# VERIFY DISPATCH
# ==================================================

assert received_action is action

assert (
    result["status"]
    == "executed"
)

assert (
    result["equipment"]
    == "webcam"
)


print(
    "[PASS] Registered action dispatched"
)


# ==================================================
# DUPLICATE REGISTRATION
# ==================================================

try:

    dispatcher.register(
        action="sense_timber",
        handler=handle_sensing,
    )

except ValueError:

    pass

else:

    raise AssertionError(
        "Duplicate action registration "
        "should fail."
    )


print(
    "[PASS] Duplicate registration rejected"
)


# ==================================================
# UNKNOWN ACTION
# ==================================================

unknown_action = Action(
    action="generate_design",
    target="design",
)


try:

    dispatcher.dispatch(
        unknown_action
    )

except KeyError:

    pass

else:

    raise AssertionError(
        "Unknown action should fail."
    )


print(
    "[PASS] Unknown action rejected"
)


# ==================================================
# INVALID HANDLER
# ==================================================

try:

    dispatcher.register(
        action="invalid_handler",
        handler=None,
    )

except TypeError:

    pass

else:

    raise AssertionError(
        "Non-callable handler should fail."
    )


print(
    "[PASS] Invalid handler rejected"
)


print()
print(
    "[test] Action dispatcher passed"
)