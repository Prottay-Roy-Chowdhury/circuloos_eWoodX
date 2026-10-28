"""Local WebSocket integration test for ROSBridgeClient.

Tests actual WebSocket communication without ROS 2.

"""

import json
import sys
import threading
import time
from pathlib import Path

from websockets.sync.server import serve


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.communication.transport.rosbridge import (
    ROSBridgeClient,
)


HOST = "127.0.0.1"
TIMEOUT = 5.0
RECONNECT_TIMEOUT = 20.0
TOPIC = "/test_rosbridge"


def wait_until(predicate, timeout=TIMEOUT):
    """Wait for an asynchronous condition."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)

    return bool(predicate())


class MockROSBridgeServer:
    """Minimal in-process ROSBridge-like WebSocket server."""

    def __init__(self):
        self.lock = threading.RLock()
        self.operations = []
        self.connections = {}
        self.next_connection_id = 0

        self.server = None
        self.thread = None
        self.port = None

    def start(self):
        self.server = serve(
            self._handle_client,
            HOST,
            0,
        )

        self.port = self.server.socket.getsockname()[1]

        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()

        print(f"[SERVER] Listening on ws://{HOST}:{self.port}")

    def _handle_client(self, websocket):
        with self.lock:
            self.next_connection_id += 1
            connection_id = self.next_connection_id
            self.connections[connection_id] = websocket

        subscribed_topics = set()

        print(f"[SERVER] Client connected: {connection_id}")

        try:
            for raw in websocket:
                message = json.loads(raw)

                op = message.get("op")
                topic = message.get("topic")

                with self.lock:
                    self.operations.append(
                        (connection_id, message)
                    )

                if op == "subscribe":
                    subscribed_topics.add(topic)

                elif op == "unsubscribe":
                    subscribed_topics.discard(topic)

                elif op == "publish":
                    # Simulate ROSBridge topic feedback.
                    # Only deliver when this session subscribed.
                    if topic in subscribed_topics:
                        websocket.send(json.dumps({
                            "op": "publish",
                            "topic": topic,
                            "msg": message.get("msg", {}),
                        }))

        except Exception as exc:
            print(f"[SERVER] Connection ended: {exc}")

        finally:
            with self.lock:
                self.connections.pop(connection_id, None)

            print(f"[SERVER] Client disconnected: {connection_id}")

    def connection_count(self):
        """Number of connections established so far."""
        with self.lock:
            return self.next_connection_id

    def has_operation(self, op, topic=TOPIC, connection_id=None):
        with self.lock:
            return any(
                message.get("op") == op
                and message.get("topic") == topic
                and (
                    connection_id is None
                    or cid == connection_id
                )
                for cid, message in self.operations
            )

    def has_published_value(self, value, connection_id=None):
        with self.lock:
            return any(
                message.get("op") == "publish"
                and message.get("topic") == TOPIC
                and message.get("msg", {}).get("data") == value
                and (
                    connection_id is None
                    or cid == connection_id
                )
                for cid, message in self.operations
            )

    def disconnect_clients(self):
        """Simulate a server-side WebSocket interruption."""
        with self.lock:
            connections = list(self.connections.values())

        for websocket in connections:
            websocket.close(
                code=1012,
                reason="Simulated server restart",
            )

    def stop(self):
        if self.server is not None:
            self.server.shutdown()

        if self.thread is not None:
            self.thread.join(timeout=5.0)

        print("[SERVER] Stopped")


def main():
    server = MockROSBridgeServer()
    client = None

    received = []
    received_lock = threading.Lock()

    def on_message(message):
        with received_lock:
            received.append(message)

        print("[CLIENT RECEIVED]", message)

    def received_value(value):
        with received_lock:
            return any(
                msg.get("data") == value
                for msg in received
            )

    def check(condition, description):
        if not condition:
            raise AssertionError(description)

        print(f"[PASS] {description}")

    try:
        server.start()

        # --------------------------------------------------
        # 1. Establish connection
        # --------------------------------------------------

        print("\n[TEST 1] Connect")

        client = ROSBridgeClient(
            host=HOST,
            port=server.port,
            timeout=TIMEOUT,
        )

        client.connect()

        check(
            client.connected,
            "WebSocket connection established",
        )

        # --------------------------------------------------
        # 2. Subscribe
        # --------------------------------------------------

        print("\n[TEST 2] Subscribe")

        client.subscribe(
            topic=TOPIC,
            msg_type="std_msgs/String",
            callback=on_message,
        )

        check(
            wait_until(
                lambda: server.has_operation("subscribe")
            ),
            "Subscription received by server",
        )

        # --------------------------------------------------
        # 3. Publish and receive
        # --------------------------------------------------

        print("\n[TEST 3] Bidirectional topic messaging")

        client.publish(
            topic=TOPIC,
            msg_type="std_msgs/String",
            message={"data": "hello_1"},
        )

        check(
            wait_until(
                lambda: server.has_operation("advertise")
            ),
            "Publisher advertisement received",
        )

        check(
            wait_until(
                lambda: server.has_published_value("hello_1")
            ),
            "JSON publish message received by server",
        )

        check(
            wait_until(lambda: received_value("hello_1")),
            "Subscribed callback received message",
        )

        # --------------------------------------------------
        # 4. Simulate connection loss
        # --------------------------------------------------

        print("\n[TEST 4] Unexpected disconnection")

        server.disconnect_clients()

        check(
            wait_until(lambda: not client.connected),
            "Client detected connection loss",
        )

        try:
            client.publish(
                topic=TOPIC,
                msg_type="std_msgs/String",
                message={"data": "during_disconnect"},
            )

        except ConnectionError:
            print("[PASS] Publish rejected while disconnected")

        else:
            raise AssertionError(
                "Disconnected publish was not rejected"
            )

        # --------------------------------------------------
        # 5. Automatic reconnection
        # --------------------------------------------------

        print("\n[TEST 5] Automatic reconnection")

        check(
            wait_until(
                lambda: (
                    client.connected
                    and server.connection_count() >= 2
                ),
                timeout=RECONNECT_TIMEOUT,
            ),
            "Client automatically reconnected",
        )

        new_connection_id = server.connection_count()

        check(
            wait_until(
                lambda: server.has_operation(
                    "subscribe",
                    connection_id=new_connection_id,
                ),
                timeout=TIMEOUT,
            ),
            "Subscription restored after reconnection",
        )

        check(
            wait_until(
                lambda: server.has_operation(
                    "advertise",
                    connection_id=new_connection_id,
                ),
                timeout=TIMEOUT,
            ),
            "Publisher restored after reconnection",
        )

        # --------------------------------------------------
        # 6. Publish again after reconnection
        # --------------------------------------------------

        print("\n[TEST 6] Communication after recovery")

        client.publish(
            topic=TOPIC,
            msg_type="std_msgs/String",
            message={"data": "hello_2"},
        )

        check(
            wait_until(
                lambda: server.has_published_value(
                    "hello_2",
                    connection_id=new_connection_id,
                )
            ),
            "Message published after reconnection",
        )

        check(
            wait_until(lambda: received_value("hello_2")),
            "Callback working after reconnection",
        )

        # --------------------------------------------------
        # 7. Clean shutdown
        # --------------------------------------------------

        print("\n[TEST 7] Clean shutdown")

        client.unsubscribe(TOPIC)
        client.unadvertise(TOPIC)
        client.close()

        check(
            wait_until(lambda: not client.connected),
            "Client disconnected on explicit close",
        )

        client.close()

        print("[PASS] Repeated close handled")

        print("\n" + "=" * 45)
        print("ROSBRIDGE WEBSOCKET INTEGRATION: PASS")
        print("=" * 45)

    except Exception as error:
        print("\n" + "=" * 45)
        print("ROSBRIDGE WEBSOCKET INTEGRATION: FAIL")
        print(f"Reason: {error}")
        print("=" * 45)
        raise

    finally:
        if client is not None:
            client.close()

        server.stop()


if __name__ == "__main__":
    main()