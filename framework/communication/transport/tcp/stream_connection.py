"""Internal bidirectional TCP JSON stream connection."""

import socket
import threading
from typing import Any, Callable, Dict

from framework.communication.transport.tcp.protocol import (
    receive_message,
    send_message,
)


MessageCallback = Callable[[Dict[str, Any]], None]
DisconnectCallback = Callable[[], None]


class TCPStreamConnection:
    """
    Manage one persistent bidirectional TCP connection.

    A background thread receives framed JSON messages.
    The owning client or server can send messages independently.

    This class does not interpret message contents or manage
    application state.
    """

    def __init__(
        self,
        sock: socket.socket,
        on_message: MessageCallback,
        on_disconnect: DisconnectCallback | None = None,
    ):
        if not callable(on_message):
            raise TypeError("on_message must be callable.")

        self._socket = sock
        self._on_message = on_message
        self._on_disconnect = on_disconnect

        self._send_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._closed = threading.Event()

        self._receive_thread: threading.Thread | None = None

    @property
    def connected(self) -> bool:
        return not self._closed.is_set()

    def start(self) -> None:
        """Start the background receive loop."""

        with self._state_lock:
            if self._closed.is_set():
                raise ConnectionError("Connection is closed.")

            if self._receive_thread is not None:
                raise RuntimeError("Receive loop already started.")

            self._receive_thread = threading.Thread(
                target=self._receive_loop,
                daemon=True,
            )

            self._receive_thread.start()

    def send(self, message: Dict[str, Any]) -> None:
        """Send one framed JSON message."""

        if not isinstance(message, dict):
            raise TypeError("message must be a dictionary.")

        with self._send_lock:
            if self._closed.is_set():
                raise ConnectionError("Connection is closed.")

            try:
                send_message(self._socket, message)
            except (OSError, ConnectionError):
                self.close()
                raise

    def close(self) -> None:
        """Close the connection and release its socket."""

        with self._state_lock:
            if self._closed.is_set():
                return

            self._closed.set()

            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            self._socket.close()

        if self._on_disconnect is not None:
            self._on_disconnect()

    def _receive_loop(self) -> None:
        """Continuously receive messages until disconnected."""

        try:
            while not self._closed.is_set():
                message = receive_message(self._socket)

                if not isinstance(message, dict):
                    raise ValueError(
                        "Stream message must be a dictionary."
                    )

                self._on_message(message)

        except (OSError, ConnectionError):
            pass

        finally:
            self.close()
