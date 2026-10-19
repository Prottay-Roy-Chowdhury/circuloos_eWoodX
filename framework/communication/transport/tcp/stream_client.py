"""Generic bidirectional TCP JSON streaming client."""

import socket
import threading
from typing import Any, Callable, Dict

from framework.communication.transport.tcp.config import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_HOST,
)
from framework.communication.transport.tcp.stream_connection import (
    TCPStreamConnection,
)


MessageCallback = Callable[[Dict[str, Any]], None]
DisconnectCallback = Callable[[], None]


class TCPStreamClient:
    """
    Persistent bidirectional TCP JSON streaming client.

    The client sends messages through a persistent connection
    and receives incoming messages in a background thread.

    Application behavior is supplied through callbacks.
    """

    def __init__(
        self,
        port: int,
        on_message: MessageCallback,
        host: str = DEFAULT_HOST,
        timeout: float = DEFAULT_CONNECT_TIMEOUT,
        on_disconnect: DisconnectCallback | None = None,
    ):
        if not callable(on_message):
            raise TypeError("on_message must be callable.")

        self.host = str(host)
        self.port = int(port)
        self.timeout = float(timeout)

        self.on_message = on_message
        self.on_disconnect = on_disconnect

        self._connection: TCPStreamConnection | None = None
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        """Whether the underlying connection is active."""

        with self._lock:
            connection = self._connection

        return (
            connection is not None
            and connection.connected
        )

    def connect(self) -> None:
        """Connect to the server and start receiving messages."""

        with self._lock:
            if (
                self._connection is not None
                and self._connection.connected
            ):
                raise RuntimeError("Client is already connected.")

            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM,
            )

            try:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))

                # The connection timeout applies only to connect().
                # The persistent receive loop must not time out
                # during normal periods without incoming data.
                sock.settimeout(None)

                connection = TCPStreamConnection(
                    sock=sock,
                    on_message=self.on_message,
                    on_disconnect=self._handle_disconnect,
                )

                self._connection = connection
                connection.start()

            except Exception:
                sock.close()
                self._connection = None
                raise

    def send(self, message: Dict[str, Any]) -> None:
        """Send one JSON message without waiting for a response."""

        with self._lock:
            connection = self._connection

        if connection is None or not connection.connected:
            raise ConnectionError("Client is not connected.")

        connection.send(message)

    def close(self) -> None:
        """Close the active streaming connection."""

        with self._lock:
            connection = self._connection

        if connection is not None:
            connection.close()

    def _handle_disconnect(self) -> None:
        """Forward disconnection notification to the application."""

        if self.on_disconnect is not None:
            self.on_disconnect()
