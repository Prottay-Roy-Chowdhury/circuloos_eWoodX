
"""Standalone integration test for bidirectional TCP streaming."""

from pathlib import Path
import sys
import socket
import threading
import time


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)

from framework.communication.transport.tcp.stream_client import (
    TCPStreamClient,
)
from framework.communication.transport.tcp.stream_server import (
    TCPStreamServer,
)


HOST = "127.0.0.1"


def wait_until(condition, timeout=5.0):
    """Wait for an asynchronous condition without fixed sleeps."""

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)

    return bool(condition())


def reserve_port():
    """Ask the OS for an available local TCP port."""

    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def main():
    port = reserve_port()

    lock = threading.Lock()

    server_received = []
    client1_received = []
    client2_received = []
    connected_ids = []
    disconnected_ids = []

    def on_server_message(client_id, message):
        with lock:
            server_received.append((client_id, message))

        print("[SERVER RECEIVED]", client_id, message)

    def on_server_connect(client_id, address):
        with lock:
            connected_ids.append(client_id)

        print("[SERVER CONNECTED]", client_id, address)

    def on_server_disconnect(client_id):
        with lock:
            disconnected_ids.append(client_id)

        print("[SERVER DISCONNECTED]", client_id)

    def on_client1_message(message):
        with lock:
            client1_received.append(message)

        print("[CLIENT 1 RECEIVED]", message)

    def on_client2_message(message):
        with lock:
            client2_received.append(message)

        print("[CLIENT 2 RECEIVED]", message)

    server = TCPStreamServer(
        host=HOST,
        port=port,
        on_message=on_server_message,
        on_connect=on_server_connect,
        on_disconnect=on_server_disconnect,
    )

    client1 = TCPStreamClient(
        host=HOST,
        port=port,
        on_message=on_client1_message,
    )

    client2 = TCPStreamClient(
        host=HOST,
        port=port,
        on_message=on_client2_message,
    )

    try:
        print("\n[TEST] Starting server")
        server.start()

        # The current start() returns before bind/listen completes.
        assert wait_until(
            lambda: server._server_socket is not None
        ), "Server did not become ready."

        print("\n[TEST] Connecting two clients")
        client1.connect()
        client2.connect()

        assert wait_until(
            lambda: len(server.client_ids) == 2
        ), "Server did not register both clients."

        print("\n[TEST] Client-to-server streaming")

        for sequence in range(5):
            client1.send({
                "source": "client1",
                "sequence": sequence,
            })

            client2.send({
                "source": "client2",
                "sequence": sequence,
            })

        assert wait_until(
            lambda: len(server_received) == 10
        ), "Server did not receive all ten messages."

        print("\n[PASS] Client-to-server messages")

        print("\n[TEST] Server broadcast")

        server.broadcast({
            "type": "broadcast",
            "value": 123,
        })

        assert wait_until(
            lambda: len(client1_received) >= 1
            and len(client2_received) >= 1
        ), "Broadcast did not reach both clients."

        assert client1_received[0]["type"] == "broadcast"
        assert client2_received[0]["type"] == "broadcast"

        print("\n[PASS] Server broadcast")

        print("\n[TEST] Targeted server messages")

        with lock:
            ids_by_source = {
                message["source"]: client_id
                for client_id, message in server_received
            }

        server.send(
            ids_by_source["client1"],
            {"type": "targeted", "target": "client1"},
        )

        server.send(
            ids_by_source["client2"],
            {"type": "targeted", "target": "client2"},
        )

        assert wait_until(
            lambda: len(client1_received) == 2
            and len(client2_received) == 2
        ), "Targeted messages were not received."

        assert client1_received[-1]["target"] == "client1"
        assert client2_received[-1]["target"] == "client2"

        print("\n[PASS] Targeted server messages")

        print("\n[TEST] Disconnecting client 1")
        client1.close()

        assert wait_until(
            lambda: len(server.client_ids) == 1
        ), "Client 1 was not removed."

        assert not client1.connected
        assert client2.connected

        print("\n[PASS] Independent client disconnection")

        print("\n[TEST] Remaining client continues streaming")

        client2.send({
            "source": "client2",
            "sequence": 99,
        })

        assert wait_until(
            lambda: any(
                message.get("sequence") == 99
                for _, message in server_received
            )
        ), "Remaining client could not send."

        print("\n[PASS] Remaining client operational")

        print("\n[TEST] Closing client 2")
        client2.close()

        assert wait_until(
            lambda: len(server.client_ids) == 0
        ), "Client 2 was not removed."

        print("\n[PASS] All clients disconnected")

        print("\n" + "=" * 50)
        print("ALL TCP STREAMING TESTS PASSED")
        print("=" * 50)

    finally:
        client1.close()
        client2.close()
        server.stop()


if __name__ == "__main__":
    main()
