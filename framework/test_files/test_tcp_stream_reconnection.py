"""Explicit TCP stream reconnection and recovery tests."""

from pathlib import Path
import socket
import sys
import threading
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.transport.tcp.stream_client import (
    TCPStreamClient,
)
from framework.communication.transport.tcp.stream_server import (
    TCPStreamServer,
)


HOST = "127.0.0.1"
TIMEOUT = 5.0
RECONNECT_CYCLES = 5


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


def main():
    port = reserve_port()
    lock = threading.Lock()

    server_received = []
    client_received = []
    client_disconnects = []
    server_disconnects = []
    connection_ids = []

    def on_server_message(client_id, message):
        with lock:
            server_received.append((client_id, message))

    def on_server_connect(client_id, address):
        with lock:
            connection_ids.append(client_id)

    def on_server_disconnect(client_id):
        with lock:
            server_disconnects.append(client_id)

    def on_client_message(message):
        with lock:
            client_received.append(message)

    def on_client_disconnect():
        with lock:
            client_disconnects.append(time.monotonic())

    server = TCPStreamServer(
        host=HOST,
        port=port,
        on_message=on_server_message,
        on_connect=on_server_connect,
        on_disconnect=on_server_disconnect,
    )

    client = TCPStreamClient(
        host=HOST,
        port=port,
        timeout=2.0,
        on_message=on_client_message,
        on_disconnect=on_client_disconnect,
    )

    def verify_bidirectional(cycle):
        """Verify both directions on the active connection."""

        client.send({
            "direction": "client_to_server",
            "cycle": cycle,
        })

        assert wait_until(
            lambda: any(
                message.get("cycle") == cycle
                and message.get("direction") == "client_to_server"
                for _, message in server_received
            )
        ), f"Server did not receive cycle {cycle}."

        with lock:
            client_id = connection_ids[-1]

        server.send(client_id, {
            "direction": "server_to_client",
            "cycle": cycle,
        })

        assert wait_until(
            lambda: any(
                message.get("cycle") == cycle
                and message.get("direction") == "server_to_client"
                for message in client_received
            )
        ), f"Client did not receive cycle {cycle}."

    try:
        print("[TEST] Connecting while server is unavailable")

        try:
            client.connect()
        except OSError:
            pass
        else:
            raise AssertionError(
                "Connection unexpectedly succeeded without server."
            )

        assert not client.connected
        print("[PASS] Initial connection failure handled")

        print("\n[TEST] Starting server and connecting")
        server.start()
        client.connect()

        assert wait_until(
            lambda: len(server.client_ids) == 1
            and len(connection_ids) == 1
        ), "Initial connection was not registered."

        assert client.connected
        print("[PASS] Connection after initial failure")

        verify_bidirectional(0)
        print("[PASS] Initial bidirectional communication")

        print("\n[TEST] Server shutdown detection")

        server.stop()

        assert wait_until(
            lambda: not client.connected
        ), "Client did not detect server shutdown."

        assert wait_until(
            lambda: len(client_disconnects) == 1
        ), "Client disconnect callback not invoked."

        assert server.client_ids == []
        print("[PASS] Server shutdown detected")

        print("\n[TEST] Repeated restart and reconnection")

        for cycle in range(1, RECONNECT_CYCLES + 1):
            previous_client_disconnects = len(client_disconnects)
            previous_server_disconnects = len(server_disconnects)
            previous_connections = len(connection_ids)

            server.start()
            client.connect()

            assert wait_until(
                lambda: len(server.client_ids) == 1
                and len(connection_ids) == previous_connections + 1
            ), f"Connection registration failed in cycle {cycle}."

            assert client.connected

            verify_bidirectional(cycle)

            server.stop()

            assert wait_until(
                lambda: not client.connected
            ), f"Client remained connected in cycle {cycle}."

            assert wait_until(
                lambda: len(client_disconnects)
                == previous_client_disconnects + 1
            ), f"Client disconnect callback count wrong in cycle {cycle}."

            assert wait_until(
                lambda: len(server_disconnects)
                == previous_server_disconnects + 1
            ), f"Server disconnect callback count wrong in cycle {cycle}."

            assert server.client_ids == []

            print(f"[PASS] Reconnection cycle {cycle}")

        with lock:
            assert len(connection_ids) == RECONNECT_CYCLES + 1
            assert len(set(connection_ids)) == len(connection_ids)
            assert len(client_disconnects) == RECONNECT_CYCLES + 1
            assert len(server_disconnects) == RECONNECT_CYCLES + 1

            expected_cycles = set(
                range(RECONNECT_CYCLES + 1)
            )

            server_cycles = {
                message["cycle"]
                for _, message in server_received
                if message.get("direction") == "client_to_server"
            }

            client_cycles = {
                message["cycle"]
                for message in client_received
                if message.get("direction") == "server_to_client"
            }

            assert server_cycles == expected_cycles
            assert client_cycles == expected_cycles

        print("\n[PASS] No duplicate disconnect callbacks")
        print("[PASS] Unique connection IDs across cycles")
        print("[PASS] Bidirectional communication recovered")

        print("\n" + "=" * 50)
        print("ALL TCP STREAM RECONNECTION TESTS PASSED")
        print("=" * 50)

    finally:
        client.close()
        server.stop()


if __name__ == "__main__":
    main()
