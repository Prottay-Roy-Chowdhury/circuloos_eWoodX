"""End-to-end offline Grasshopper-to-ServoMaster test.

No ROS, Grasshopper or robot required.
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
    end = time.monotonic() + timeout

    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)

    return predicate()


def check(condition, name):
    if not condition:
        raise AssertionError(name)

    print(f"[PASS] {name}")


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
        update_hz=20.0,
        input_timeout=0.5,
    )

    inbox = queue.Queue()

    gh_client = TCPStreamClient(
        host=HOST,
        port=gh_port,
        on_message=inbox.put,
    )

    def send_gh(message):
        gh_client.send(message)

        response = inbox.get(timeout=2.0)

        assert response["type"] == "gh_ack"
        assert response["request"] == message["type"]

        return response

    def send_axes(session, seq, linear, angular):
        return send_gh({
            "type": "gh_axes",
            "session": session,
            "seq": seq,
            "linear": linear,
            "angular": angular,
        })

    def master_state():
        return master.state.snapshot()

    try:
        master.start()
        control.start()
        gh_client.connect()

        print("\n[TEST 1] Both TCP channels")

        check(
            control.client.registered,
            "Control agent registered with master",
        )

        check(
            gh_client.connected,
            "Simulated GH connected to control agent",
        )

        print("\n[TEST 2] GH arm and master arm")

        reply = send_gh({"type": "gh_arm"})
        check(reply["accepted"], "GH session armed")

        session1 = reply["state"]["session"]

        reply = send_axes(
            session1,
            0,
            [0, 0, 0],
            [0, 0, 0],
        )
        check(reply["accepted"], "Initial heartbeat accepted")

        check(
            wait_until(
                lambda: (
                    control.status()["master_armed"]
                    and master_state()["armed"]
                )
            ),
            "Master explicitly armed by coordinator",
        )

        print("\n[TEST 3] Direction propagation")

        reply = send_axes(
            session1,
            1,
            [1, 0, -1],
            [0, 1, 0],
        )

        check(reply["accepted"], "Six-axis update accepted")

        check(
            wait_until(
                lambda: (
                    master_state()["linear"] == [1, 0, -1]
                    and master_state()["angular"] == [0, 1, 0]
                )
            ),
            "Six-axis command reached master",
        )

        print("\n[TEST 4] Continuous refresh")

        first_seq = master_state()["last_seq"]

        # Keep GH input alive while checking the independent
        # master-side publish sequence.
        for seq in range(2, 8):
            reply = send_axes(
                session1,
                seq,
                [1, 0, -1],
                [0, 1, 0],
            )
            check(reply["accepted"], f"Heartbeat {seq}")
            time.sleep(0.05)

        check(
            master_state()["last_seq"] > first_seq,
            "Independent master-side sequence advanced",
        )

        print("\n[TEST 5] GH stop propagates")

        reply = send_gh({"type": "gh_stop"})
        check(reply["accepted"], "GH stop accepted")

        check(
            wait_until(
                lambda: not master_state()["armed"]
            ),
            "Stop disarmed master",
        )

        check(
            master_state()["linear"] == [0, 0, 0]
            and master_state()["angular"] == [0, 0, 0],
            "Master axes cleared",
        )

        print("\n[TEST 6] New session, no old motion")

        reply = send_gh({"type": "gh_arm"})
        session2 = reply["state"]["session"]

        check(
            session2 != session1,
            "New input session created",
        )

        reply = send_axes(
            session2,
            0,
            [0, 0, 0],
            [0, 0, 0],
        )

        check(reply["accepted"], "New heartbeat accepted")

        check(
            wait_until(lambda: master_state()["armed"]),
            "Master rearmed explicitly",
        )

        reply = send_axes(
            session2,
            1,
            [0, 0, 1],
            [0, 0, 0],
        )

        check(reply["accepted"], "New direction accepted")

        check(
            wait_until(
                lambda: master_state()["linear"] == [0, 0, 1]
            ),
            "New direction reached master",
        )

        print("\n[TEST 7] GH heartbeat timeout")

        # Stop sending GH updates while leaving TCP open.
        check(
            wait_until(
                lambda: (
                    control.gh.snapshot()["reason"]
                    == "input_timeout"
                ),
                timeout=2.0,
            ),
            "GH watchdog expired",
        )

        check(
            wait_until(
                lambda: not master_state()["armed"]
            ),
            "GH timeout disarmed master",
        )

        check(
            master_state()["linear"] == [0, 0, 0],
            "Master cleared stale command",
        )

        print("\n[TEST 8] No automatic rearming")

        reply = send_axes(
            session2,
            2,
            [1, 0, 0],
            [0, 0, 0],
        )

        check(
            not reply["accepted"],
            "Old GH session rejected after timeout",
        )

        check(
            not master_state()["armed"],
            "Master remains disarmed",
        )

        print("\n" + "=" * 52)
        print("END-TO-END GH TCP CONTROL PIPELINE: PASS")
        print("=" * 52)

    finally:
        gh_client.close()
        control.stop()
        master.stop()


if __name__ == "__main__":
    main()