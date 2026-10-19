"""Stress-test concurrent TCP client connection and server shutdown."""

from pathlib import Path
import socket
import sys
import threading
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.transport.tcp.stream_server import (
    TCPStreamServer,
)


HOST = "127.0.0.1"
CYCLES = 30
CLIENTS_PER_CYCLE = 12


def reserve_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def test_shutdown_race():
    port = reserve_port()
    errors = []
    lock = threading.Lock()

    server = TCPStreamServer(
        host=HOST,
        port=port,
        accept_timeout=0.1,
        on_message=lambda client_id, message: None,
    )

    original_excepthook = threading.excepthook

    def capture_thread_exception(args):
        with lock:
            errors.append(args.exc_value)

    threading.excepthook = capture_thread_exception

    try:
        for cycle in range(CYCLES):
            sockets = []
            sockets_lock = threading.Lock()
            start_event = threading.Event()

            server.start()

            def connect_client():
                start_event.wait()

                sock = socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                )
                sock.settimeout(1.0)

                try:
                    sock.connect((HOST, port))

                    with sockets_lock:
                        sockets.append(sock)

                except OSError:
                    # Connection refusal during shutdown
                    # is an expected outcome.
                    sock.close()

            threads = [
                threading.Thread(target=connect_client)
                for _ in range(CLIENTS_PER_CYCLE)
            ]

            try:
                for thread in threads:
                    thread.start()

                # Release connection attempts concurrently.
                start_event.set()

                # Race shutdown against pending connections.
                server.stop()

                for thread in threads:
                    thread.join(timeout=3.0)
                    assert not thread.is_alive(), (
                        "Client connection thread did not finish."
                    )

                assert not server.running
                assert server.client_ids == [], (
                    f"Stale connections after cycle {cycle + 1}"
                )

                with lock:
                    assert not errors, (
                        f"Background thread errors: {errors}"
                    )

                print(
                    f"[PASS] Shutdown race cycle {cycle + 1}"
                )

            finally:
                for sock in sockets:
                    sock.close()

                server.stop()

        print("\n" + "=" * 50)
        print("ALL TCP STREAM SHUTDOWN RACE TESTS PASSED")
        print("=" * 50)

    finally:
        server.stop()
        threading.excepthook = original_excepthook


if __name__ == "__main__":
    test_shutdown_race()
