"""Integration test for Agent-aware bidirectional streaming."""

from pathlib import Path
import socket
import sys
import threading
import time


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


from framework.communication.core import Agent
from framework.communication.workflow.stream_client import (
    StreamClient,
)
from framework.communication.workflow.stream_handler import (
    StreamHandler,
)
from framework.communication.transport import TCPStreamClient


HOST = "127.0.0.1"


def reserve_port():
    """Reserve an available localhost TCP port."""

    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def wait_until(condition, timeout=5.0):
    """Wait for asynchronous operations."""

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)

    return bool(condition())


def main():

    port = reserve_port()
    lock = threading.Lock()

    master_received = []
    agent1_received = []
    agent2_received = []

    def on_master_message(agent, message):
        with lock:
            master_received.append(
                (agent.agent_id, message)
            )

        print(
            "[MASTER RECEIVED]",
            agent.agent_id,
            message,
        )

    def on_agent1_message(message):
        with lock:
            agent1_received.append(message)

        print("[AGENT 1 RECEIVED]", message)

    def on_agent2_message(message):
        with lock:
            agent2_received.append(message)

        print("[AGENT 2 RECEIVED]", message)

    master = StreamHandler(
        host=HOST,
        port=port,
        on_message=on_master_message,
    )

    agent1 = StreamClient(
        agent=Agent(
            agent_id="sensing_pc_01",
            roles=["sensing"],
        ),
        host=HOST,
        port=port,
        on_message=on_agent1_message,
    )

    agent2 = StreamClient(
        agent=Agent(
            agent_id="processing_pc_01",
            roles=["processing"],
        ),
        host=HOST,
        port=port,
        on_message=on_agent2_message,
    )

    try:

        # --------------------------------------------------
        # 1. Start Master
        # --------------------------------------------------

        print("\n[TEST 1] Start streaming Master")

        master.start()

        assert master.tcp_server.running

        print("[PASS] Master started")

        # --------------------------------------------------
        # 2. Register two Agents
        # --------------------------------------------------

        print("\n[TEST 2] Connect and register Agents")

        agent1.connect()
        agent2.connect()

        assert wait_until(
            lambda: set(master.connected_agents) == {
                "sensing_pc_01",
                "processing_pc_01",
            }
        ), "Agents did not register."

        assert agent1.connected
        assert agent2.connected

        print("[PASS] Both Agents registered")

        # --------------------------------------------------
        # 3. Agent -> Master
        # --------------------------------------------------

        print("\n[TEST 3] Agent-to-Master streaming")

        agent1.send({
            "type": "sensor_data",
            "value": 42,
        })

        agent2.send({
            "type": "processing_data",
            "value": 99,
        })

        assert wait_until(
            lambda: len(master_received) == 2
        ), "Master did not receive both messages."

        with lock:
            received_by_agent = {
                agent_id: message
                for agent_id, message in master_received
            }

        assert (
            received_by_agent["sensing_pc_01"]["value"]
            == 42
        )

        assert (
            received_by_agent["processing_pc_01"]["value"]
            == 99
        )

        print("[PASS] Agent messages identified correctly")

        # --------------------------------------------------
        # 4. Master -> Agent
        # --------------------------------------------------

        print("\n[TEST 4] Targeted Master-to-Agent streaming")

        master.send(
            "sensing_pc_01",
            {
                "type": "control",
                "value": "start",
            },
        )

        master.send(
            "processing_pc_01",
            {
                "type": "control",
                "value": "stop",
            },
        )

        assert wait_until(
            lambda: len(agent1_received) == 1
            and len(agent2_received) == 1
        ), "Agents did not receive targeted messages."

        assert agent1_received[0]["value"] == "start"
        assert agent2_received[0]["value"] == "stop"

        print("[PASS] Targeted messages delivered")

        # --------------------------------------------------
        # 5. Independent disconnection
        # --------------------------------------------------

        print("\n[TEST 5] Disconnect Agent 1")

        agent1.close()

        assert wait_until(
            lambda: master.connected_agents
            == ["processing_pc_01"]
        ), "Agent 1 registration was not removed."

        assert not agent1.connected
        assert agent2.connected

        print("[PASS] Agent 2 remains connected")

        # --------------------------------------------------
        # 6. Remaining Agent continues
        # --------------------------------------------------

        print("\n[TEST 6] Remaining Agent continues")

        agent2.send({
            "type": "processing_data",
            "value": 100,
        })

        assert wait_until(
            lambda: any(
                agent_id == "processing_pc_01"
                and message.get("value") == 100
                for agent_id, message in master_received
            )
        ), "Remaining Agent could not send."

        print("[PASS] Remaining Agent operational")

        # --------------------------------------------------
        # 7. Reconnection
        # --------------------------------------------------

        print("\n[TEST 7] Agent reconnection")

        agent1.connect()

        assert wait_until(
            lambda: "sensing_pc_01"
            in master.connected_agents
        ), "Agent did not register after reconnecting."

        assert agent1.connected

        print("[PASS] Agent reconnected")


        # --------------------------------------------------
        # 8. Duplicate Agent ID
        # --------------------------------------------------

        print("\n[TEST 8] Duplicate Agent registration")

        duplicate = StreamClient(
            agent=Agent(
                agent_id="sensing_pc_01",
                roles=["sensing"],
            ),
            host=HOST,
            port=port,
            on_message=lambda message: None,
        )

        try:
            try:
                duplicate.connect()

            except ConnectionError as error:
                assert "Agent already connected" in str(error)
                print("[EXPECTED REJECTION]", error)

            else:
                raise AssertionError(
                    "Duplicate Agent registration was accepted."
                )

            assert not duplicate.connected
            assert not duplicate.registered

            assert agent1.connected
            assert agent1.registered

            assert "sensing_pc_01" in master.connected_agents

            print("[PASS] Duplicate Agent rejected")

        finally:
            duplicate.close()



        # --------------------------------------------------
        # 9. Unregistered transport client
        # --------------------------------------------------

        print("\n[TEST 9] Reject unregistered connection")

        raw_received = []
        raw_lock = threading.Lock()

        def on_raw_message(message):
            with raw_lock:
                raw_received.append(message)

        raw_client = TCPStreamClient(
            host=HOST,
            port=port,
            on_message=on_raw_message,
        )

        try:
            raw_client.connect()

            raw_client.send({
                "type": "sensor_data",
                "value": -1,
            })

            assert wait_until(
                lambda: any(
                    message.get("type") == "agent_rejected"
                    for message in raw_received
                )
            ), "Unregistered client received no rejection."

            with raw_lock:
                rejection = next(
                    message
                    for message in raw_received
                    if message.get("type") == "agent_rejected"
                )

            assert (
                "has not registered"
                in rejection["reason"]
            )

            print(
                "[EXPECTED REJECTION]",
                rejection["reason"],
            )

            assert not any(
                message.get("value") == -1
                for _, message in master_received
            ), "Unregistered message reached application handler."

            print("[PASS] Unregistered client rejected")

        finally:
            raw_client.close()


        # --------------------------------------------------
        # 10. Shutdown
        # --------------------------------------------------

        print("\n[TEST 10] Controlled shutdown")

        agent1.close()
        agent2.close()

        assert wait_until(
            lambda: len(master.connected_agents) == 0
        )

        master.stop()

        assert not master.tcp_server.running

        print("[PASS] Controlled shutdown")

        print("\n" + "=" * 55)
        print("ALL STREAM WORKFLOW TESTS PASSED")
        print("=" * 55)

    finally:
        agent1.close()
        agent2.close()
        master.stop()


if __name__ == "__main__":
    main()
