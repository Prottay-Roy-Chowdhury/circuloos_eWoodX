
"""Offline fault-injection tests for the two-sided Servo pipeline.

Tests:
1. Grasshopper TCP disconnection during active motion
2. Master TCP disconnection during active motion
3. Master rejecting an active axis command
4. Service restart and stale-session rejection

No ROS, Rhino, Grasshopper, or robot required.
"""

from pathlib import Path
import sys
import queue
import socket
import time
from contextlib import contextmanager

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.transport.tcp import TCPStreamClient

from projects.servo_teleop.agents.master_agent import ServoMaster
from projects.servo_teleop.agents.control_agent import ServoControlAgent


HOST = "127.0.0.1"
WAIT_TIMEOUT = 3.0


def free_port():
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def wait_until(predicate, timeout=WAIT_TIMEOUT):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)

    return bool(predicate())


def check(condition, description):
    if not condition:
        raise AssertionError(description)

    print(f"[PASS] {description}")


def measure_transition(action, predicate, description):
    """Measure observed completion after a deliberate fault."""
    start = time.monotonic()
    action()

    check(
        wait_until(predicate),
        description,
    )

    elapsed_ms = (time.monotonic() - start) * 1000
    print(f"       Observed transition: {elapsed_ms:.1f} ms")


@contextmanager
def running_stack():
    """Start an isolated master, control agent and GH client."""
    master_port = free_port()
    gh_port = free_port()

    while gh_port == master_port:
        gh_port = free_port()

    master = ServoMaster(
        host=HOST,
        port=master_port,
        command_timeout=0.3,
    )

    control = ServoControlAgent(
        master_host=HOST,
        master_port=master_port,
        gh_host=HOST,
        gh_port=gh_port,
        update_hz=20.0,
        input_timeout=0.5,
        arm_timeout=2.0,
    )

    inbox = queue.Queue()

    gh = TCPStreamClient(
        host=HOST,
        port=gh_port,
        on_message=inbox.put,
    )

    try:
        master.start()
        control.start()
        gh.connect()

        check(
            control.client.registered,
            "Control agent registered with master",
        )
        check(
            gh.connected,
            "Simulated Grasshopper connected",
        )

        yield master, control, gh, inbox

    finally:
        gh.close()
        control.stop()
        master.stop()


def send_gh(client, inbox, message):
    client.send(message)
    reply = inbox.get(timeout=2.0)

    if (
        reply.get("type") != "gh_ack"
        or reply.get("request") != message.get("type")
    ):
        raise AssertionError(
            f"Unexpected GH acknowledgement: {reply}"
        )

    return reply


def send_axes(
    client,
    inbox,
    session,
    seq,
    linear,
    angular=(0, 0, 0),
):
    return send_gh(client, inbox, {
        "type": "gh_axes",
        "session": session,
        "seq": seq,
        "linear": list(linear),
        "angular": list(angular),
    })


def arm_and_move(master, control, gh, inbox):
    """Establish a valid moving state for fault injection."""

    reply = send_gh(
        gh, inbox, {"type": "gh_arm"}
    )

    check(reply["accepted"], "GH session armed")
    session = reply["state"]["session"]

    reply = send_axes(
        gh, inbox, session, 0,
        linear=(1, 0, 0),
    )
    check(reply["accepted"], "Nonzero command accepted")

    check(
        wait_until(
            lambda: (
                control.status()["master_armed"]
                and master.state.snapshot()["armed"]
                and master.state.snapshot()["linear"]
                == [1, 0, 0]
            )
        ),
        "Master received active motion state",
    )

    return session


def assert_disarmed(master, control):
    check(
        wait_until(
            lambda: not master.state.snapshot()["armed"]
        ),
        "Master disarmed",
    )

    state = master.state.snapshot()

    check(
        state["linear"] == [0, 0, 0]
        and state["angular"] == [0, 0, 0],
        "Master motion axes cleared",
    )

    check(
        not control.gh.snapshot()["armed"],
        "GH input session invalidated",
    )


def test_gh_disconnect():
    print("\n" + "=" * 56)
    print("TEST 1: GH DISCONNECT DURING ACTIVE MOTION")
    print("=" * 56)

    with running_stack() as (master, control, gh, inbox):
        arm_and_move(master, control, gh, inbox)

        measure_transition(
            action=gh.close,
            predicate=lambda: (
                not master.state.snapshot()["armed"]
                and not control.gh.snapshot()["armed"]
            ),
            description="GH disconnect propagated to master",
        )

        assert_disarmed(master, control)

        check(
            control.gh.snapshot()["reason"]
            == "owner_disconnected",
            "GH disarm reason is owner_disconnected",
        )

        check(
            control.client.registered,
            "Master TCP connection remains available",
        )


def test_master_disconnect():
    print("\n" + "=" * 56)
    print("TEST 2: MASTER DISCONNECT DURING ACTIVE MOTION")
    print("=" * 56)

    with running_stack() as (master, control, gh, inbox):
        arm_and_move(master, control, gh, inbox)

        # Deliberately stop only the master-facing TCP server.
        # The master state monitor remains running.
        measure_transition(
            action=master.handler.stop,
            predicate=lambda: (
                control._stop_event.is_set()
                and not control.gh.snapshot()["armed"]
                and not master.state.snapshot()["armed"]
            ),
            description="Master disconnect halted coordinator",
        )

        check(
            control.status()["master_fault"],
            "Master-side fault recorded",
        )

        check(
            not control.client.registered,
            "Control agent detected lost master connection",
        )

        assert_disarmed(master, control)

        check(
            control.gh.snapshot()["reason"]
            == "explicit_stop",
            "GH input invalidated after master fault",
        )


def test_master_rejection():
    print("\n" + "=" * 56)
    print("TEST 3: MASTER REJECTS ACTIVE COMMAND")
    print("=" * 56)

    with running_stack() as (master, control, gh, inbox):
        arm_and_move(master, control, gh, inbox)

        # Simulate a master-side authorization loss.
        # The next servo_axes command from the coordinator
        # should be rejected because the master is disarmed.
        #
        # This does not mock or modify the TCP transport.
        measure_transition(
            action=lambda: master.state.apply(
                "system",
                {"type": "servo_stop"},
            ),
            predicate=lambda: (
                control.status()["master_fault"]
                and control._stop_event.is_set()
                and not control.gh.snapshot()["armed"]
            ),
            description="Rejected command invalidated coordinator",
        )

        assert_disarmed(master, control)

        check(
            gh.connected,
            "GH socket may remain connected while disarmed",
        )

        check(
            control.client.registered,
            "Master TCP transport remains connected",
        )

        # New GH arm may be locally acknowledged,
        # but a stopped coordinator must not forward motion.
        reply = send_gh(
            gh, inbox, {"type": "gh_arm"}
        )
        check(
            reply["accepted"],
            "GH interface still responds locally",
        )

        new_session = reply["state"]["session"]

        reply = send_axes(
            gh, inbox, new_session, 0,
            linear=(1, 0, 0),
        )
        check(
            reply["accepted"],
            "GH interface accepts local input only",
        )

        time.sleep(0.15)

        check(
            not master.state.snapshot()["armed"],
            "Faulted coordinator does not rearm master",
        )


def test_service_restart():
    print("\n" + "=" * 56)
    print("TEST 4: SERVICE RESTART AND SESSION ISOLATION")
    print("=" * 56)

    old_session = None

    print("\n[PHASE A] Original service instance")

    with running_stack() as (master, control, gh, inbox):
        old_session = arm_and_move(
            master, control, gh, inbox
        )

        check(
            bool(old_session),
            "Original GH session recorded",
        )

    print("\n[PHASE B] Fresh service instance")

    with running_stack() as (master, control, gh, inbox):
        check(
            not master.state.snapshot()["armed"],
            "Restarted master begins disarmed",
        )

        check(
            not control.gh.snapshot()["armed"],
            "Restarted GH interface begins disarmed",
        )

        reply = send_axes(
            gh, inbox, old_session, 1,
            linear=(1, 0, 0),
        )

        check(
            not reply["accepted"],
            "Old motion rejected without new arm",
        )

        reply = send_gh(
            gh, inbox, {"type": "gh_arm"}
        )

        check(
            reply["accepted"],
            "Explicit new GH arm accepted",
        )

        new_session = reply["state"]["session"]

        check(
            new_session != old_session,
            "Restart generated a different session ID",
        )

        reply = send_axes(
            gh, inbox, old_session, 2,
            linear=(1, 0, 0),
        )

        check(
            not reply["accepted"],
            "Old session token rejected after new arm",
        )

        check(
            not master.state.snapshot()["armed"],
            "Master remains disarmed before valid heartbeat",
        )

        # Fresh session must explicitly send new input.
        reply = send_axes(
            gh, inbox, new_session, 0,
            linear=(0, 0, 0),
        )

        check(
            reply["accepted"],
            "Fresh zero-direction heartbeat accepted",
        )

        check(
            wait_until(
                lambda: master.state.snapshot()["armed"]
            ),
            "Master armed from fresh session",
        )

        check(
            master.state.snapshot()["linear"]
            == [0, 0, 0],
            "Previous nonzero motion was not restored",
        )


def main():
    test_gh_disconnect()
    test_master_disconnect()
    test_master_rejection()
    test_service_restart()

    print("\n" + "=" * 56)
    print("GH CONTROL FAILURE-INJECTION TEST: PASS")
    print("=" * 56)


if __name__ == "__main__":
    main()