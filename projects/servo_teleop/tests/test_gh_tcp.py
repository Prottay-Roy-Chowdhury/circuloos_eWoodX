"""Offline integration test for Grasshopper TCP interface.

"""

from pathlib import Path
import sys
import queue
import socket
import time

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.transport.tcp import (
    TCPStreamClient,
)
from projects.servo_teleop.operations.grasshopper_tcp import (
    GrasshopperTCPInterface,
)


HOST = "127.0.0.1"


def free_port():
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    print(f"[PASS] {description}")


def main():
    port = free_port()

    interface = GrasshopperTCPInterface(
        host=HOST,
        port=port,
        input_timeout=0.5,
    )

    inbox1 = queue.Queue()
    inbox2 = queue.Queue()

    client1 = TCPStreamClient(
        host=HOST,
        port=port,
        on_message=inbox1.put,
    )

    client2 = TCPStreamClient(
        host=HOST,
        port=port,
        on_message=inbox2.put,
    )

    def request(client, inbox, message):
        client.send(message)
        reply = inbox.get(timeout=2.0)
        check(
            reply.get("type") == "gh_ack",
            f"Acknowledgement for {message['type']}",
        )
        return reply

    try:
        interface.start()
        client1.connect()
        client2.connect()

        print("\n[TEST 1] Connection")
        check(
            client1.connected and client2.connected,
            "Both simulated GH clients connected",
        )

        print("\n[TEST 2] Unarmed command")
        reply = request(client1, inbox1, {
            "type": "gh_axes",
            "session": "invalid",
            "seq": 0,
            "linear": [1, 0, 0],
            "angular": [0, 0, 0],
        })
        check(
            not reply["accepted"],
            "Unarmed movement rejected",
        )

        print("\n[TEST 3] Explicit arm")
        reply = request(client1, inbox1, {
            "type": "gh_arm"
        })
        check(reply["accepted"], "First client armed")

        session1 = reply["state"]["session"]
        check(bool(session1), "Session ID assigned")

        print("\n[TEST 4] Single control owner")
        reply = request(client2, inbox2, {
            "type": "gh_arm"
        })
        check(
            not reply["accepted"],
            "Second client cannot take control",
        )

        print("\n[TEST 5] Six-axis command")
        reply = request(client1, inbox1, {
            "type": "gh_axes",
            "session": session1,
            "seq": 0,
            "linear": [1, 0, -1],
            "angular": [0, 1, 0],
        })
        check(
            reply["accepted"]
            and reply["state"]["linear"] == [1, 0, -1]
            and reply["state"]["angular"] == [0, 1, 0],
            "Input state updated",
        )

        print("\n[TEST 6] Duplicate sequence")
        reply = request(client1, inbox1, {
            "type": "gh_axes",
            "session": session1,
            "seq": 0,
            "linear": [-1, 0, 0],
            "angular": [0, 0, 0],
        })
        check(
            not reply["accepted"],
            "Duplicate sequence rejected",
        )

        print("\n[TEST 7] Different client")
        reply = request(client2, inbox2, {
            "type": "gh_axes",
            "session": session1,
            "seq": 1,
            "linear": [-1, 0, 0],
            "angular": [0, 0, 0],
        })
        check(
            not reply["accepted"],
            "Non-owner command rejected",
        )

        print("\n[TEST 8] Invalid axis values")
        reply = request(client1, inbox1, {
            "type": "gh_axes",
            "session": session1,
            "seq": 1,
            "linear": [0.5, 0, 0],
            "angular": [0, 0, 0],
        })
        check(
            not reply["accepted"],
            "Non-discrete direction rejected",
        )

        print("\n[TEST 9] Heartbeat refresh")
        # Re-send unchanged direction with increasing
        # sequence numbers. This represents a GH heartbeat.
        for seq in range(1, 6):
            reply = request(client1, inbox1, {
                "type": "gh_axes",
                "session": session1,
                "seq": seq,
                "linear": [1, 0, -1],
                "angular": [0, 1, 0],
            })
            check(
                reply["accepted"],
                f"Heartbeat {seq} accepted",
            )
            time.sleep(0.05)

        check(
            interface.snapshot()["armed"],
            "Heartbeat maintained input session",
        )

        print("\n[TEST 10] Input timeout")
        time.sleep(0.65)

        state = interface.snapshot()
        check(
            not state["armed"]
            and state["reason"] == "input_timeout"
            and state["linear"] == [0, 0, 0],
            "Stale input disarmed and reset",
        )

        print("\n[TEST 11] Old session invalid")
        reply = request(client1, inbox1, {
            "type": "gh_axes",
            "session": session1,
            "seq": 6,
            "linear": [1, 0, 0],
            "angular": [0, 0, 0],
        })
        check(
            not reply["accepted"],
            "Old command rejected after timeout",
        )

        print("\n[TEST 12] Fresh session")
        reply = request(client1, inbox1, {
            "type": "gh_arm"
        })
        check(reply["accepted"], "Rearmed explicitly")

        session2 = reply["state"]["session"]
        check(
            session2 != session1,
            "New arm created a different session",
        )

        reply = request(client1, inbox1, {
            "type": "gh_axes",
            "session": session1,
            "seq": 7,
            "linear": [1, 0, 0],
            "angular": [0, 0, 0],
        })
        check(
            not reply["accepted"],
            "Previous session token rejected",
        )

        print("\n[TEST 13] Explicit stop")
        reply = request(client1, inbox1, {
            "type": "gh_stop"
        })
        check(
            reply["accepted"]
            and not reply["state"]["armed"],
            "Explicit stop disarmed input",
        )

        print("\n[TEST 14] Disconnect")
        reply = request(client1, inbox1, {
            "type": "gh_arm"
        })
        check(reply["accepted"], "Armed before disconnect")

        client1.close()

        deadline = time.monotonic() + 2.0
        while (
            interface.snapshot()["armed"]
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)

        check(
            not interface.snapshot()["armed"]
            and interface.snapshot()["reason"]
            == "owner_disconnected",
            "Owner disconnect disarmed input",
        )

        print("\n[TEST 15] New client can arm")
        reply = request(client2, inbox2, {
            "type": "gh_arm"
        })
        check(
            reply["accepted"],
            "Second client can arm after owner disconnect",
        )

        print("\n" + "=" * 48)
        print("GRASSHOPPER TCP INTERFACE TEST: PASS")
        print("=" * 48)

    finally:
        client1.close()
        client2.close()
        interface.stop()


if __name__ == "__main__":
    main()