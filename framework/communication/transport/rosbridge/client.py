"""Generic ROSBridge transport using roslibpy.

Independent of robot type, ROS message type, and application.

Lifecycle:
    connect() -> publish/subscribe -> close()

roslibpy handles unexpected WebSocket reconnection internally.
An explicitly closed client is not reused.
"""

import threading
from typing import Callable, Dict, Optional

import roslibpy


class ROSBridgeClient:
    """Reusable ROSBridge topic publishing/subscription client."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9090,
        timeout: float = 5.0,
    ):
        if not host or not isinstance(host, str):
            raise ValueError("host must be a non-empty string")
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.host = host
        self.port = port
        self.timeout = float(timeout)

        self._ros: Optional[roslibpy.Ros] = None
        self._publishers: Dict[str, roslibpy.Topic] = {}
        self._subscribers: Dict[str, roslibpy.Topic] = {}

        self._lock = threading.RLock()
        self._closed = False

    @property
    def connected(self) -> bool:
        """Current WebSocket connection state."""
        with self._lock:
            ros = self._ros
        return bool(ros is not None and ros.is_connected)

    def connect(self) -> None:
        """Start ROSBridge connection and wait until ready.

        This method blocks for up to ``timeout`` seconds.
        Call it from a worker or master process, not a GUI loop.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError(
                    "Client has been closed; create a new instance."
                )

            if self._ros is not None:
                raise RuntimeError(
                    "Connection already initialized."
                )

            ros = roslibpy.Ros(
                host=self.host,
                port=self.port,
            )
            self._ros = ros

        try:
            ros.run(timeout=self.timeout)

            if not ros.is_connected:
                raise ConnectionError(
                    "ROSBridge did not establish a connection."
                )

        except Exception:
            with self._lock:
                self._closed = True

            # Do not terminate the shared Twisted reactor here.
            # roslibpy may still have a reconnect attempt running.
            try:
                ros.close()
            except Exception:
                pass
            raise

    def _require_connection(self) -> roslibpy.Ros:
        """Return the active connection or reject operations."""
        with self._lock:
            if self._closed or self._ros is None:
                raise ConnectionError(
                    "ROSBridge client is not initialized."
                )

            ros = self._ros

        if not ros.is_connected:
            raise ConnectionError(
                "ROSBridge is disconnected."
            )

        return ros

    def advertise(
        self,
        topic: str,
        msg_type: str,
    ) -> None:
        """Register a ROS topic publisher."""
        ros = self._require_connection()

        if not topic or not msg_type:
            raise ValueError(
                "topic and msg_type must be non-empty."
            )

        with self._lock:
            existing = self._publishers.get(topic)

            if existing is not None:
                if existing.message_type != msg_type:
                    raise ValueError(
                        f"Topic {topic} already advertised "
                        "with another message type."
                    )
                return

            publisher = roslibpy.Topic(
                ros,
                topic,
                msg_type,
                latch=False,
                reconnect_on_close=True,
            )

            publisher.advertise()
            self._publishers[topic] = publisher

    def publish(
        self,
        topic: str,
        msg_type: str,
        message: dict,
    ) -> None:
        """Publish one ROS-compatible message dictionary.

        A publisher is automatically advertised on first use.
        Publishing while disconnected raises ConnectionError.
        """
        if not isinstance(message, dict):
            raise TypeError("message must be a dictionary")

        self._require_connection()
        self.advertise(topic, msg_type)

        with self._lock:
            publisher = self._publishers[topic]

        # Recheck before sending. This cannot eliminate a
        # disconnect during transmission, but rejects known loss.
        self._require_connection()
        publisher.publish(roslibpy.Message(message))

    def subscribe(
        self,
        topic: str,
        msg_type: str,
        callback: Callable[[dict], None],
    ) -> None:
        """Subscribe to a topic with an asynchronous callback.

        One callback per topic is supported by this wrapper.
        Callbacks should be short and non-blocking.
        """
        ros = self._require_connection()

        if not topic or not msg_type:
            raise ValueError(
                "topic and msg_type must be non-empty."
            )
        if not callable(callback):
            raise TypeError("callback must be callable")

        with self._lock:
            if topic in self._subscribers:
                raise ValueError(
                    f"Already subscribed to {topic}"
                )

            subscriber = roslibpy.Topic(
                ros,
                topic,
                msg_type,
                reconnect_on_close=True,
            )

            subscriber.subscribe(callback)
            self._subscribers[topic] = subscriber

    def unsubscribe(self, topic: str) -> None:
        """Remove a previously registered subscription."""
        with self._lock:
            subscriber = self._subscribers.pop(topic, None)

        if subscriber is not None:
            subscriber.unsubscribe()

    def unadvertise(self, topic: str) -> None:
        """Remove a previously registered publisher."""
        with self._lock:
            publisher = self._publishers.pop(topic, None)

        if publisher is not None:
            publisher.unadvertise()

    def close(self) -> None:
        """Release topics and explicitly close the connection.

        Idempotent. Automatic reconnect is not used after close().
        Does not terminate the shared roslibpy event loop.
        """
        with self._lock:
            if self._closed:
                return

            self._closed = True
            publishers = list(self._publishers.values())
            subscribers = list(self._subscribers.values())

            self._publishers.clear()
            self._subscribers.clear()

            ros = self._ros

        for subscriber in subscribers:
            try:
                subscriber.unsubscribe()
            except Exception:
                pass

        for publisher in publishers:
            try:
                publisher.unadvertise()
            except Exception:
                pass

        if ros is not None:
            try:
                ros.close(timeout=self.timeout)
            except Exception:
                pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False