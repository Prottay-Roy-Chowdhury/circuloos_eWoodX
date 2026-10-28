"""Offline master session and request-correlation test.

"""
from pathlib import Path
import sys
import queue
import socket
import time
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.core import Agent
from framework.communication.workflow import StreamClient
from projects.servo_teleop.agents.master_agent import ServoMaster


HOST = "127.0.0.1"


def free_port():
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def check(condition, label):
    assert condition, label
    print("[PASS]", label)


def main():
    port = free_port()
    inbox = queue.Queue()

    master = ServoMaster(
        host=HOST,
        port=port,
        command_timeout=1.0,
    )

    client = StreamClient(
        agent=Agent(
            agent_id="session_test_agent",
            roles=["servo_control"],
        ),
        host=HOST,
        port=port,
        on_message=inbox.put,
    )

    def request(command):
        message = dict(command)
        message["request_id"] = uuid.uuid4().hex

        client.send(message)
        ack = inbox.get(timeout=2.0)

        check(
            ack["type"] == "servo_ack"
            and ack["request"] == message["type"]
            and ack["request_id"] == message["request_id"],
            f"Correlated {message['type']} acknowledgement",
        )
        return ack

    def axes(session, seq, linear):
        return request({
            "type": "servo_axes",
            "session": session,
            "seq": seq,
            "linear": linear,
            "angular": [0, 0, 0],
        })

    try:
        master.start()
        client.connect()

        print("\n[1] Session creation")
        ack = request({"type": "servo_arm"})
        check(ack["accepted"], "Arm accepted")
        session1 = ack["state"]["session"]
        check(bool(session1), "Master session created")

        print("\n[2] Valid movement")
        ack = axes(session1, 0, [1, 0, 0])
        check(ack["accepted"], "Correct session accepted")

        print("\n[3] Wrong session")
        ack = axes("invalid-session", 1, [-1, 0, 0])
        check(not ack["accepted"], "Wrong session rejected")
        check(
            master.state.snapshot()["linear"] == [1, 0, 0],
            "Rejected command did not change axes",
        )

        print("\n[4] Duplicate sequence")
        ack = axes(session1, 0, [-1, 0, 0])
        check(not ack["accepted"], "Duplicate sequence rejected")

        print("\n[5] Stop invalidates session")
        ack = request({"type": "servo_stop"})
        check(
            ack["accepted"] and not ack["state"]["armed"],
            "Stop disarmed master",
        )

        print("\n[6] New arm")
        ack = request({"type": "servo_arm"})
        session2 = ack["state"]["session"]
        check(
            session2 != session1,
            "New session differs from previous session",
        )

        print("\n[7] Old movement after new arm")
        ack = axes(session1, 1, [1, 0, 0])
        check(
            not ack["accepted"],
            "Previous-session movement rejected",
        )
        check(
            master.state.snapshot()["linear"] == [0, 0, 0],
            "Old movement not restored",
        )

        print("\n[8] New session movement")
        ack = axes(session2, 0, [0, 1, 0])
        check(ack["accepted"], "New session command accepted")

        print("\n[9] Session timeout")
        time.sleep(1.15)
        state = master.state.snapshot()
        check(
            not state["armed"]
            and state["session"] is None
            and state["reason"] == "command_timeout",
            "Timeout invalidated master session",
        )

        print("\n[10] Expired session cannot move")
        ack = axes(session2, 1, [1, 0, 0])
        check(
            not ack["accepted"],
            "Expired session command rejected",
        )

        print("\n" + "=" * 52)
        print("MASTER SESSION PROTOCOL TEST: PASS")
        print("=" * 52)

    finally:
        client.close()
        master.stop()


if __name__ == "__main__":
    main()