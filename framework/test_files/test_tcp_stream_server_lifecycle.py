"""Startup and shutdown tests for TCPStreamServer."""

from pathlib import Path
import sys
import socket
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


def reserve_port():
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)

    return bool(condition())


def test_startup():
    port = reserve_port()

    server = TCPStreamServer(
        host=HOST,
        port=port,
        on_message=lambda client_id, message: None,
    )

    try:
        server.start()

        assert server.running
        print("[PASS] Server startup")

        try:
            server.start()
        except RuntimeError:
            print("[PASS] Duplicate startup rejected")
        else:
            raise AssertionError(
                "Duplicate startup was not rejected."
            )

    finally:
        server.stop()

    assert not server.running
    print("[PASS] Server shutdown")


def test_port_conflict():
    port = reserve_port()

    server1 = TCPStreamServer(
        host=HOST,
        port=port,
        on_message=lambda client_id, message: None,
    )

    server2 = TCPStreamServer(
        host=HOST,
        port=port,
        on_message=lambda client_id, message: None,
    )

    try:
        server1.start()

        try:
            server2.start()
        except OSError:
            print("[PASS] Port conflict reported")
        else:
            raise AssertionError(
                "Port conflict was not reported."
            )

        assert server1.running
        assert not server2.running

    finally:
        server2.stop()
        server1.stop()


def test_restart():
    port = reserve_port()

    server = TCPStreamServer(
        host=HOST,
        port=port,
        on_message=lambda client_id, message: None,
    )

    try:
        server.start()
        assert server.running

        server.stop()
        assert not server.running

        server.start()
        assert server.running

        print("[PASS] Server restart")

    finally:
        server.stop()


def test_shutdown_with_client():
    port = reserve_port()

    server = TCPStreamServer(
        host=HOST,
        port=port,
        on_message=lambda client_id, message: None,
    )

    client = TCPStreamClient(
        host=HOST,
        port=port,
        on_message=lambda message: None,
    )

    try:
        server.start()
        client.connect()

        assert wait_until(
            lambda: len(server.client_ids) == 1
        )

        server.stop()

        assert not server.running

        assert wait_until(
            lambda: not client.connected
        ), "Client did not detect server shutdown."

        assert server.client_ids == []

        print("[PASS] Shutdown with active client")

    finally:
        client.close()
        server.stop()


def main():
    test_startup()
    test_port_conflict()
    test_restart()
    test_shutdown_with_client()

    print()
    print("=" * 50)
    print("ALL TCP STREAM SERVER LIFECYCLE TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    main()
