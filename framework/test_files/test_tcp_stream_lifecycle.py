"""Lifecycle tests for TCPStreamConnection."""

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

from framework.communication.transport.tcp.stream_connection import (
    TCPStreamConnection,
)


def wait_until(condition, timeout=3.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)

    return bool(condition())


def test_concurrent_close():
    """Concurrent close calls must notify exactly once."""

    sock1, sock2 = socket.socketpair()

    disconnect_count = []
    lock = threading.Lock()

    def on_disconnect():
        with lock:
            disconnect_count.append(1)

    connection = TCPStreamConnection(
        sock=sock1,
        on_message=lambda message: None,
        on_disconnect=on_disconnect,
    )

    connection.start()

    threads = [
        threading.Thread(target=connection.close)
        for _ in range(10)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=2.0)
        assert not thread.is_alive()

    assert not connection.connected
    assert len(disconnect_count) == 1

    sock2.close()

    print("[PASS] Concurrent close")


def test_callback_exception():
    """Message callback errors must be reported and cleaned up."""

    sock1, sock2 = socket.socketpair()

    errors = []
    disconnected = threading.Event()

    def on_message(message):
        raise RuntimeError("Test callback failure")

    connection = TCPStreamConnection(
        sock=sock1,
        on_message=on_message,
        on_disconnect=disconnected.set,
        on_error=errors.append,
    )

    connection.start()

    from framework.communication.transport.tcp.protocol import (
        send_message,
    )

    send_message(
        sock2,
        {"type": "test"},
    )

    assert disconnected.wait(timeout=3.0)
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert not connection.connected

    sock2.close()

    print("[PASS] Callback exception handling")


def test_disconnect_callback_exception():
    """Disconnect callback errors must not interrupt cleanup."""

    sock1, sock2 = socket.socketpair()

    errors = []

    def on_disconnect():
        raise RuntimeError("Disconnect callback failure")

    connection = TCPStreamConnection(
        sock=sock1,
        on_message=lambda message: None,
        on_disconnect=on_disconnect,
        on_error=errors.append,
    )

    connection.start()
    connection.close()

    assert not connection.connected
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)

    sock2.close()

    print("[PASS] Disconnect callback exception handling")


def main():
    test_concurrent_close()
    test_callback_exception()
    test_disconnect_callback_exception()

    print()
    print("=" * 50)
    print("ALL TCP STREAM LIFECYCLE TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    main()
