
"""Offline acknowledgement-watchdog and GH fault-feedback test.

Run:
    python -m projects.servo_teleop.tests.test_gh_ack_watchdog
"""

from pathlib import Path
import sys
import queue
import socket
import time

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.transport.tcp import TCPStreamClient

from projects.servo_teleop.agents.master_agent import ServoMaster
from projects.servo_teleop.agents.control_agent import ServoControlAgent


HOST = "127.0.0.1"


def free_port():
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)

    return bool(predicate())


def check(condition, label):
    assert condition, label
    print("[PASS]", label)


def main():
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
        input_timeout=0.5,
        ack_timeout=0.25,
        max_pending_axes=10,
        update_hz=20.0,
    )

    inbox = queue.Queue()

    gh = TCPStreamClient(
        host=HOST,
        port=gh_port,
        on_message=inbox.put,
    )

    original_send = master.handler.send
    drop_axis_ack = False
    dropped_count = 0

    def filtered_send(agent_id, message):
        nonlocal dropped_count

        if (
            drop_axis_ack
            and message.get("type") == "servo_ack"
            and message.get("request") == "servo_axes"
        ):
            dropped_count += 1
            return

        return original_send(agent_id, message)

    def request(message):
        gh.send(message)
        response = inbox.get(timeout=2.0)

        assert response["type"] == "gh_ack"
        assert response["request"] == message["type"]
        return response

    def axes(session, seq, linear):
        return request({
            "type": "gh_axes",
            "session": session,
            "seq": seq,
            "linear": linear,
            "angular": [0, 0, 0],
        })

    try:
        # Patch only the test instance's master response path.
        # Master still processes incoming commands normally.
        master.handler.send = filtered_send

        master.start()
        control.start()
        gh.connect()

        print("\n[1] Healthy communication")

        reply = request({"type": "gh_status"})
        check(
            reply["control"]["state"] == "READY",
            "GH reports READY",
        )

        reply = request({"type": "gh_arm"})
        check(reply["accepted"], "GH arm accepted")

        session = reply["state"]["session"]

        reply = axes(session, 0, [0, 0, 0])
        check(reply["accepted"], "Initial heartbeat accepted")

        check(
            wait_until(
                lambda: control.status()["master_armed"]
            ),
            "Master armed",
        )

        print("\n[2] Simulate lost master acknowledgements")

        drop_axis_ack = True

        seen_master_motion = False
        seq = 1
        maximum_pending = 0

        # Keep GH input fresh while deliberately dropping
        # only acknowledgements from the master.
        deadline = time.monotonic() + 1.5

        while time.monotonic() < deadline:
            reply = axes(session, seq, [1, 0, 0])

            if not reply["accepted"]:
                break

            seq += 1

            if master.state.snapshot()["linear"] == [1, 0, 0]:
                seen_master_motion = True

            maximum_pending = max(
                maximum_pending,
                control.status()["pending_axes"],
            )

            if control.status()["state"] == "FAULT":
                break

            time.sleep(0.05)

        check(
            seen_master_motion,
            "Master received commands despite lost ACKs",
        )

        check(
            dropped_count > 0,
            "Master acknowledgements were suppressed",
        )

        check(
            wait_until(
                lambda: control.status()["state"] == "FAULT"
            ),
            "ACK watchdog triggered FAULT",
        )

        check(
            control.status()["reason"] in (
                "master_axis_ack_timeout",
                "master_axis_ack_backlog",
            ),
            "Fault identifies missing ACK or backlog",
        )

        check(
            maximum_pending <= 10,
            "Outstanding requests remained bounded",
        )

        print("\n[3] Master stop and GH invalidation")

        check(
            wait_until(
                lambda: (
                    not master.state.snapshot()["armed"]
                    and not control.gh.snapshot()["armed"]
                )
            ),
            "Master and GH disarmed after ACK failure",
        )

        check(
            master.state.snapshot()["linear"] == [0, 0, 0],
            "Master axes cleared",
        )

        print("\n[4] GH operational feedback")

        reply = request({"type": "gh_status"})

        check(
            reply["control"]["state"] == "FAULT",
            "GH reports coordinator FAULT",
        )

        reply = request({"type": "gh_arm"})

        check(
            not reply["accepted"],
            "GH arming blocked while faulted",
        )

        check(
            reply["control"]["state"] == "FAULT",
            "Rejection includes fault status",
        )

        print("\n" + "=" * 55)
        print("GH ACK WATCHDOG AND FAULT FEEDBACK TEST: PASS")
        print("=" * 55)

    finally:
        master.handler.send = original_send
        gh.close()
        control.stop()
        master.stop()


if __name__ == "__main__":
    main()