"""Test TCP stream server shutdown during on_connect callback."""

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
TIMEOUT = 5.0


def reserve_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def test_callback_shutdown():
    port = reserve_port()

    callback_started = threading.Event()
    callback_release = threading.Event()
    callback_finished = threading.Event()
    stop_started = threading.Event()
    stop_finished = threading.Event()

    callback_ids = []
    stop_errors = []

    def on_connect(client_id, address):
        callback_ids.append(client_id)

        print("[TEST] on_connect callback started")
        callback_started.set()

        # Hold callback execution until the test releases it.
        if not callback_release.wait(timeout=TIMEOUT):
            raise TimeoutError(
                "Callback release was not received."
            )

        callback_finished.set()
        print("[TEST] on_connect callback finished")

    server = TCPStreamServer(
        host=HOST,
        port=port,
        accept_timeout=0.1,
        on_message=lambda client_id, message: None,
        on_connect=on_connect,
    )

    def stop_server():
        stop_started.set()

        try:
            server.stop()
        except Exception as exc:
            stop_errors.append(exc)
        finally:
            stop_finished.set()

    client_socket = None
    stop_thread = None

    try:
        server.start()

        client_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )
        client_socket.settimeout(2.0)
        client_socket.connect((HOST, port))

        assert callback_started.wait(timeout=TIMEOUT), (
            "on_connect callback did not start."
        )

        print("[PASS] Callback entered")

        assert len(callback_ids) == 1
        assert len(server.client_ids) == 1

        stop_thread = threading.Thread(
            target=stop_server,
            name="test-server-stop",
        )
        stop_thread.start()

        assert stop_started.wait(timeout=TIMEOUT)

        # Allow stop() to begin while callback remains blocked.
        time.sleep(0.2)

        print(
            "[RESULT] stop_finished_before_release:",
            stop_finished.is_set(),
        )

        # Release callback regardless of whether stop()
        # has already returned.
        callback_release.set()

        assert callback_finished.wait(timeout=TIMEOUT), (
            "Callback did not finish."
        )

        stop_thread.join(timeout=TIMEOUT)

        assert not stop_thread.is_alive(), (
            "Server stop thread did not finish."
        )

        assert stop_finished.is_set()
        assert not stop_errors, (
            f"Server stop raised errors: {stop_errors}"
        )

        assert not server.running
        assert server.client_ids == []

        print("[PASS] Callback completed")
        print("[PASS] Server shutdown completed")
        print("[PASS] No stale registered connections")

        print("\n" + "=" * 50)
        print("TCP STREAM CALLBACK SHUTDOWN TEST COMPLETED")
        print("=" * 50)

    finally:
        callback_release.set()

        if client_socket is not None:
            client_socket.close()

        if stop_thread is not None:
            stop_thread.join(timeout=TIMEOUT)

        server.stop()


if __name__ == "__main__":
    test_callback_shutdown()
