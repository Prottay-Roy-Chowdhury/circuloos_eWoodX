"""Robustness tests for Agent-aware streaming workflows."""

from pathlib import Path
import socket
import sys
import threading
import time


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


from framework.communication.core import Agent
from framework.communication.transport import TCPStreamClient
from framework.communication.workflow.stream_client import StreamClient
from framework.communication.workflow.stream_handler import StreamHandler


HOST = "127.0.0.1"
TIMEOUT = 5.0


def reserve_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def wait_until(condition, timeout=TIMEOUT):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)

    return bool(condition())


def make_client(agent_id, port):
    return StreamClient(
        agent=Agent(agent_id=agent_id, roles=["testing"]),
        host=HOST,
        port=port,
        on_message=lambda message: None,
        registration_timeout=2.0,
    )


def make_master(port, received):
    return StreamHandler(
        host=HOST,
        port=port,
        on_message=lambda agent, message: received.append(
            (agent.agent_id, message)
        ),
    )


def test_invalid_registrations():
    print("\n[TEST 1] Invalid registration payloads")

    port = reserve_port()
    received = []
    master = make_master(port, received)
    master.start()

    invalid_payloads = [
        {
            "type": "agent_register",
        },
        {
            "type": "agent_register",
            "agent": None,
        },
        {
            "type": "agent_register",
            "agent": {},
        },
        {
            "type": "agent_register",
            "agent": {
                "agent_id": "",
                "roles": [],
            },
        },
        {
            "type": "agent_register",
            "agent": {
                "agent_id": "invalid_agent",
                "roles": [],
                "metadata": ["invalid"],
            },
        },
    ]

    try:
        for index, payload in enumerate(invalid_payloads):
            responses = []
            lock = threading.Lock()

            def on_message(message):
                with lock:
                    responses.append(message)

            client = TCPStreamClient(
                host=HOST,
                port=port,
                on_message=on_message,
            )

            try:
                client.connect()
                client.send(payload)

                def rejected():
                    with lock:
                        return any(
                            msg.get("type") == "agent_rejected"
                            for msg in responses
                        )

                assert wait_until(rejected), (
                    f"Invalid payload {index} was not rejected."
                )

                with lock:
                    rejection = next(
                        msg for msg in responses
                        if msg.get("type") == "agent_rejected"
                    )

                assert "Invalid Agent registration" in (
                    rejection["reason"]
                )

                assert not master.connected_agents

                print(
                    f"[PASS] Invalid payload {index + 1} rejected"
                )

            finally:
                client.close()

        assert received == []
        print("[PASS] Invalid messages did not reach application")

    finally:
        master.stop()


def test_concurrent_duplicate_registration():
    print("\n[TEST 2] Concurrent duplicate registrations")

    port = reserve_port()
    received = []
    master = make_master(port, received)
    master.start()

    clients = [
        make_client("concurrent_agent", port),
        make_client("concurrent_agent", port),
    ]

    barrier = threading.Barrier(3)
    results = []
    lock = threading.Lock()

    def connect_client(index):
        try:
            barrier.wait(timeout=TIMEOUT)
            clients[index].connect()
            outcome = ("accepted", index, None)

        except Exception as error:
            outcome = ("rejected", index, error)

        with lock:
            results.append(outcome)

    threads = [
        threading.Thread(
            target=connect_client,
            args=(index,),
        )
        for index in range(2)
    ]

    try:
        for thread in threads:
            thread.start()

        barrier.wait(timeout=TIMEOUT)

        for thread in threads:
            thread.join(timeout=TIMEOUT)
            assert not thread.is_alive(), (
                "Concurrent registration thread did not finish."
            )

        accepted = [
            result for result in results
            if result[0] == "accepted"
        ]

        rejected = [
            result for result in results
            if result[0] == "rejected"
        ]

        assert len(accepted) == 1, results
        assert len(rejected) == 1, results

        assert isinstance(rejected[0][2], ConnectionError)
        assert "Agent already connected" in str(rejected[0][2])

        assert master.connected_agents == [
            "concurrent_agent"
        ]

        winner = clients[accepted[0][1]]
        loser = clients[rejected[0][1]]

        assert winner.registered
        assert not loser.registered

        print("[PASS] Exactly one registration accepted")
        print("[PASS] Duplicate registration rejected")

    finally:
        for client in clients:
            client.close()
        master.stop()


def test_registration_timeout():
    print("\n[TEST 3] Registration acknowledgement timeout")

    port = reserve_port()

    # A real TCP listener that accepts connections but does
    # not send registration acknowledgements.
    listener = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    listener.bind((HOST, port))
    listener.listen(1)
    listener.settimeout(TIMEOUT)

    accepted = threading.Event()
    release = threading.Event()
    server_errors = []

    def silent_server():
        connection = None

        try:
            connection, _ = listener.accept()
            accepted.set()

            # Keep the connection open without responding.
            release.wait(timeout=TIMEOUT)

        except Exception as error:
            server_errors.append(error)

        finally:
            if connection is not None:
                connection.close()

    server_thread = threading.Thread(
        target=silent_server,
        daemon=True,
    )

    server_thread.start()

    client = StreamClient(
        agent=Agent(
            agent_id="timeout_agent",
            roles=["testing"],
        ),
        host=HOST,
        port=port,
        on_message=lambda message: None,
        registration_timeout=0.3,
    )

    try:
        started = time.monotonic()

        try:
            client.connect()

        except TimeoutError as error:
            assert "acknowledgement timed out" in str(error)

        else:
            raise AssertionError(
                "Registration succeeded without acknowledgement."
            )

        elapsed = time.monotonic() - started

        assert accepted.is_set()
        assert elapsed < 2.0, (
            f"Registration timeout took too long: {elapsed:.3f}s"
        )

        assert not client.connected
        assert not client.registered

        print(
            f"[PASS] Registration timed out after {elapsed:.3f}s"
        )
        print("[PASS] Client connection cleaned up")

    finally:
        client.close()
        release.set()
        listener.close()
        server_thread.join(timeout=TIMEOUT)

    assert not server_thread.is_alive()
    assert not server_errors, server_errors


def test_reconnection_after_rejection():
    print("\n[TEST 4] Reconnection after rejection")

    port = reserve_port()
    received = []
    master = make_master(port, received)
    master.start()

    original = make_client("reconnect_agent", port)
    duplicate = make_client("reconnect_agent", port)

    try:
        original.connect()

        assert original.registered
        assert master.connected_agents == ["reconnect_agent"]

        try:
            duplicate.connect()

        except ConnectionError as error:
            assert "Agent already connected" in str(error)

        else:
            raise AssertionError(
                "Duplicate registration was accepted."
            )

        assert not duplicate.registered
        assert original.registered

        print("[PASS] Initial duplicate rejected")

        original.close()

        assert wait_until(
            lambda: "reconnect_agent"
            not in master.connected_agents
        ), "Original registration was not released."

        duplicate.connect()

        assert duplicate.registered
        assert duplicate.connected

        print("[PASS] Previously rejected Agent registered")

        duplicate.send({
            "type": "reconnection_test",
            "value": 123,
        })

        assert wait_until(
            lambda: any(
                agent_id == "reconnect_agent"
                and message.get("value") == 123
                for agent_id, message in received
            )
        ), "Reconnected Agent could not send."

        print("[PASS] Reconnected Agent can communicate")

    finally:
        original.close()
        duplicate.close()
        master.stop()


def test_master_shutdown_restart():
    print("\n[TEST 5] Master shutdown and restart")

    port = reserve_port()
    received = []
    master = make_master(port, received)

    agent1 = make_client("restart_agent_1", port)
    agent2 = make_client("restart_agent_2", port)

    try:
        master.start()

        agent1.connect()
        agent2.connect()

        assert set(master.connected_agents) == {
            "restart_agent_1",
            "restart_agent_2",
        }

        print("[PASS] Agents registered before shutdown")

        master.stop()

        assert wait_until(
            lambda: not agent1.connected
            and not agent2.connected
        ), "Agents did not detect Master shutdown."

        assert wait_until(
            lambda: len(master.connected_agents) == 0
        ), "Master retained stale registrations."

        assert not agent1.registered
        assert not agent2.registered

        print("[PASS] Connections closed")
        print("[PASS] Registrations cleared")

        master.start()

        assert master.tcp_server.running

        agent1.connect()
        agent2.connect()

        assert set(master.connected_agents) == {
            "restart_agent_1",
            "restart_agent_2",
        }

        assert agent1.registered
        assert agent2.registered

        print("[PASS] Same Master restarted")
        print("[PASS] Both Agents registered again")

    finally:
        agent1.close()
        agent2.close()
        master.stop()


def main():
    tests = [
        test_invalid_registrations,
        test_concurrent_duplicate_registration,
        test_registration_timeout,
        test_reconnection_after_rejection,
        test_master_shutdown_restart,
    ]

    print("=" * 60)
    print("STREAM WORKFLOW ROBUSTNESS TESTS")
    print("=" * 60)

    passed = 0

    for test in tests:
        try:
            test()
            passed += 1

        except Exception:
            print(f"\n[FAILED] {test.__name__}")
            raise

    print("\n" + "=" * 60)
    print(f"ALL {passed} STREAM WORKFLOW ROBUSTNESS TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
