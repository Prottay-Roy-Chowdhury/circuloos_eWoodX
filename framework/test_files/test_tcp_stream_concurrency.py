"""Sustained concurrent bidirectional TCP streaming test."""

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

from framework.communication.transport.tcp.stream_client import TCPStreamClient
from framework.communication.transport.tcp.stream_server import TCPStreamServer


HOST = "127.0.0.1"
CLIENT_COUNT = 4
MESSAGES_PER_CLIENT = 1000
TIMEOUT = 30.0


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
    server_received = {i: [] for i in range(CLIENT_COUNT)}
    client_received = {i: [] for i in range(CLIENT_COUNT)}
    client_ids = {}
    errors = []
    disconnects = []

    def on_server_message(client_id, message):
        with lock:
            if message["type"] == "register":
                client_ids[message["client"]] = client_id
            elif message["type"] == "data":
                server_received[message["client"]].append(
                    message["sequence"]
                )

    def on_disconnect(client_id):
        with lock:
            disconnects.append(client_id)

    def make_callback(index):
        def callback(message):
            with lock:
                if (
                    message["type"] != "data"
                    or message["client"] != index
                ):
                    errors.append(
                        AssertionError("Unexpected client message")
                    )
                else:
                    client_received[index].append(
                        message["sequence"]
                    )
        return callback

    server = TCPStreamServer(
        host=HOST,
        port=port,
        on_message=on_server_message,
        on_disconnect=on_disconnect,
    )
    clients = [
        TCPStreamClient(
            host=HOST,
            port=port,
            on_message=make_callback(i),
        )
        for i in range(CLIENT_COUNT)
    ]

    def client_sender(index):
        try:
            for sequence in range(MESSAGES_PER_CLIENT):
                clients[index].send({
                    "type": "data",
                    "client": index,
                    "sequence": sequence,
                })
        except Exception as exc:
            with lock:
                errors.append(exc)

    def server_sender(index):
        try:
            for sequence in range(MESSAGES_PER_CLIENT):
                server.send(client_ids[index], {
                    "type": "data",
                    "client": index,
                    "sequence": sequence,
                })
        except Exception as exc:
            with lock:
                errors.append(exc)

    try:
        server.start()

        for index, client in enumerate(clients):
            client.connect()
            client.send({
                "type": "register",
                "client": index,
            })

        assert wait_until(
            lambda: len(client_ids) == CLIENT_COUNT
        ), "Registration timeout."

        threads = []
        start_time = time.monotonic()

        for index in range(CLIENT_COUNT):
            threads.append(
                threading.Thread(
                    target=client_sender,
                    args=(index,),
                )
            )
            threads.append(
                threading.Thread(
                    target=server_sender,
                    args=(index,),
                )
            )

        print("[TEST] Starting concurrent bidirectional traffic")

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=TIMEOUT)

        assert all(
            not thread.is_alive() for thread in threads
        ), "A sending thread did not finish."

        assert wait_until(
            lambda: all(
                len(server_received[i]) == MESSAGES_PER_CLIENT
                and len(client_received[i]) == MESSAGES_PER_CLIENT
                for i in range(CLIENT_COUNT)
            )
        ), "Message delivery timeout."

        expected = list(range(MESSAGES_PER_CLIENT))

        with lock:
            assert not errors, f"Errors: {errors}"
            assert not disconnects, "Unexpected disconnection"

            for index in range(CLIENT_COUNT):
                assert server_received[index] == expected, (
                    f"Server ordering failure for client {index}"
                )
                assert client_received[index] == expected, (
                    f"Client ordering failure for client {index}"
                )

        elapsed = time.monotonic() - start_time
        total = CLIENT_COUNT * MESSAGES_PER_CLIENT * 2

        print("[PASS] All messages delivered")
        print("[PASS] Message ordering preserved")
        print("[PASS] No unexpected disconnections")
        print(f"[RESULT] Messages: {total}")
        print(f"[RESULT] Duration: {elapsed:.3f} seconds")
        print(f"[RESULT] Throughput: {total / elapsed:.1f} msg/s")

        print("=" * 50)
        print("ALL TCP STREAM CONCURRENCY TESTS PASSED")
        print("=" * 50)

    finally:
        for client in clients:
            client.close()
        server.stop()


if __name__ == "__main__":
    main()
