"""Offline Servo teleoperation integration test.

Uses the existing TCP StreamClient and StreamHandler.
No ROS, ROSBridge, Grasshopper, or robot required.

"""

from pathlib import Path
import socket
import sys
import threading
import time


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.core import Agent
from framework.communication.workflow import StreamClient
from projects.servo_teleop.agents.master_agent import ServoMaster


HOST = "127.0.0.1"


def available_port():
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


def check(condition, description):
    if not condition:
        raise AssertionError(description)

    print(f"[PASS] {description}")


def main():
    port = available_port()

    master = ServoMaster(
        host=HOST,
        port=port,
        command_timeout=0.3,
    )

    responses = []
    response_lock = threading.Lock()

    def on_message(message):
        with response_lock:
            responses.append(message)

    def get_responses():
        with response_lock:
            return list(responses)

    agent = StreamClient(
        agent=Agent(
            agent_id="grasshopper_test_agent",
            roles=["servo_control"],
        ),
        host=HOST,
        port=port,
        on_message=on_message,
    )

    def send_and_wait(message):
        previous_count = len(get_responses())

        agent.send(message)

        check(
            wait_until(
                lambda: len(get_responses()) > previous_count
            ),
            f"Acknowledgement for {message['type']}",
        )

        return get_responses()[-1]

    try:
        master.start()

        # ----------------------------------------------
        # Test 1: Agent registration
        # ----------------------------------------------

        print("\n[TEST 1] Agent registration")

        agent.connect()

        check(
            agent.registered,
            "Control agent registered",
        )

        # ----------------------------------------------
        # Test 2: Reject movement before arming
        # ----------------------------------------------

        print("\n[TEST 2] Reject unarmed motion")

        response = send_and_wait({
            "type": "servo_axes",
            "seq": 0,
            "linear": [1, 0, 0],
            "angular": [0, 0, 0],
        })

        check(
            response["accepted"] is False,
            "Movement rejected while disarmed",
        )

        # ----------------------------------------------
        # Test 3: Explicitly arm
        # ----------------------------------------------

        print("\n[TEST 3] Arm control session")

        response = send_and_wait({
            "type": "servo_arm",
        })

        check(
            response["accepted"] is True
            and response["state"]["armed"],
            "Control session armed",
        )

        # ----------------------------------------------
        # Test 4: Continuous axis updates
        # ----------------------------------------------

        print("\n[TEST 4] Continuous axis updates")

        for seq in range(10):
            response = send_and_wait({
                "type": "servo_axes",
                "seq": seq,
                "linear": [1, 0, -1],
                "angular": [0, 0, 0],
            })

            check(
                response["accepted"],
                f"Axis command {seq} accepted",
            )

            time.sleep(0.05)

        state = master.state.snapshot()

        check(
            state["linear"] == [1, 0, -1]
            and state["last_seq"] == 9,
            "Latest command state maintained",
        )

        # ----------------------------------------------
        # Test 5: Reject stale sequence
        # ----------------------------------------------

        print("\n[TEST 5] Sequence validation")

        response = send_and_wait({
            "type": "servo_axes",
            "seq": 8,
            "linear": [-1, 0, 0],
            "angular": [0, 0, 0],
        })

        check(
            response["accepted"] is False,
            "Old sequence rejected",
        )

        # ----------------------------------------------
        # Test 6: Explicit stop
        # ----------------------------------------------

        print("\n[TEST 6] Explicit stop")

        response = send_and_wait({
            "type": "servo_stop",
        })

        check(
            response["accepted"]
            and not response["state"]["armed"]
            and response["state"]["linear"] == [0, 0, 0],
            "Stop clears motion and disarms",
        )

        # ----------------------------------------------
        # Test 7: Command timeout
        # ----------------------------------------------

        print("\n[TEST 7] Command timeout")

        send_and_wait({"type": "servo_arm"})

        send_and_wait({
            "type": "servo_axes",
            "seq": 0,
            "linear": [0, 1, 0],
            "angular": [0, 0, 0],
        })

        check(
            wait_until(
                lambda: (
                    master.state.snapshot()["reason"]
                    == "command_timeout"
                ),
                timeout=2.0,
            ),
            "Control disarmed after command timeout",
        )

        check(
            master.state.snapshot()["linear"] == [0, 0, 0],
            "Expired command reset to zero",
        )

        # ----------------------------------------------
        # Test 8: No automatic rearming
        # ----------------------------------------------

        print("\n[TEST 8] No automatic rearming")

        response = send_and_wait({
            "type": "servo_axes",
            "seq": 1,
            "linear": [1, 0, 0],
            "angular": [0, 0, 0],
        })

        check(
            response["accepted"] is False,
            "Motion requires explicit rearming",
        )

        # ----------------------------------------------
        # Test 9: Agent disconnection
        # ----------------------------------------------

        print("\n[TEST 9] Agent disconnection")

        send_and_wait({"type": "servo_arm"})

        send_and_wait({
            "type": "servo_axes",
            "seq": 0,
            "linear": [1, 0, 0],
            "angular": [0, 0, 0],
        })

        agent.close()

        check(
            wait_until(
                lambda: (
                    master.state.snapshot()["reason"]
                    == "owner_disconnected"
                )
            ),
            "Disconnection disarms the control session",
        )

        # ----------------------------------------------
        # Test 10: Reconnect without automatic motion
        # ----------------------------------------------

        print("\n[TEST 10] Agent reconnection")

        agent.connect()

        check(
            agent.registered,
            "Agent registered again",
        )

        check(
            not master.state.snapshot()["armed"],
            "Reconnection does not automatically arm",
        )

        print("\n" + "=" * 48)
        print("OFFLINE SERVO TELEOP TEST: PASS")
        print("=" * 48)

    finally:
        agent.close()
        master.stop()


if __name__ == "__main__":
    main()