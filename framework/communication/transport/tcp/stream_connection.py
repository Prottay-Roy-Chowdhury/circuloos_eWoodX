"""Internal bidirectional TCP JSON stream connection."""

import socket
import threading
import traceback
from typing import Any, Callable, Dict

from framework.communication.transport.tcp.protocol import (
    receive_message,
    send_message,
)


MessageCallback = Callable[[Dict[str, Any]], None]
DisconnectCallback = Callable[[], None]
ErrorCallback = Callable[[Exception], None]


class TCPStreamConnection:
    """
    Manage one persistent bidirectional TCP connection.

    A background thread receives framed JSON messages.
    Sending is independently synchronized.

    The connection owns socket lifecycle only.
    Application behavior is supplied through callbacks.
    """

    def __init__(
        self,
        sock: socket.socket,
        on_message: MessageCallback,
        on_disconnect: DisconnectCallback | None = None,
        on_error: ErrorCallback | None = None,
    ):
        if not callable(on_message):
            raise TypeError("on_message must be callable.")

        self._socket = sock

        self._on_message = on_message
        self._on_disconnect = on_disconnect
        self._on_error = on_error

        self._send_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._closed = threading.Event()

        self._receive_thread: threading.Thread | None = None

    @property
    def connected(self) -> bool:
        """Return whether the connection remains open."""

        return not self._closed.is_set()

    def start(self) -> None:
        """Start the background receive loop once."""

        with self._state_lock:
            if self._closed.is_set():
                raise ConnectionError("Connection is closed.")

            if self._receive_thread is not None:
                raise RuntimeError(
                    "Receive loop already started."
                )

            self._receive_thread = threading.Thread(
                target=self._receive_loop,
                name="tcp-stream-receiver",
                daemon=True,
            )

            self._receive_thread.start()

    def send(self, message: Dict[str, Any]) -> None:
        """Send one framed JSON message."""

        if not isinstance(message, dict):
            raise TypeError(
                "message must be a dictionary."
            )

        try:
            with self._send_lock:
                if self._closed.is_set():
                    raise ConnectionError(
                        "Connection is closed."
                    )

                send_message(
                    self._socket,
                    message,
                )

        except (OSError, ConnectionError):
            # Close outside the send lock.
            self.close()
            raise

    def close(self) -> None:
        """
        Close the socket and notify the application once.

        Socket shutdown is performed outside the state lock.
        This avoids holding the lifecycle lock during socket
        operations or application callbacks.
        """

        with self._state_lock:
            if self._closed.is_set():
                return

            self._closed.set()

        try:
            self._socket.shutdown(
                socket.SHUT_RDWR
            )
        except OSError:
            pass

        try:
            self._socket.close()
        except OSError:
            pass

        if self._on_disconnect is not None:
            try:
                self._on_disconnect()
            except Exception as exc:
                self._report_error(exc)

    def _receive_loop(self) -> None:
        """Receive messages until the connection closes."""

        try:
            while not self._closed.is_set():

                message = receive_message(
                    self._socket
                )

                if not isinstance(message, dict):
                    raise ValueError(
                        "Stream message must be a dictionary."
                    )

                self._on_message(message)

        except ConnectionError:
            # A remote peer may close its socket normally.
            # Treat this as a disconnection, not an
            # application error.
            pass

        except OSError as exc:
            # Report unexpected socket errors unless
            # shutdown was already requested locally.
            if not self._closed.is_set():
                self._report_error(exc)

        except Exception as exc:
            # Invalid messages and application callback
            # exceptions remain reportable errors.
            if not self._closed.is_set():
                self._report_error(exc)

        finally:
            self.close()

    def _report_error(self, exc: Exception) -> None:
        """
        Report a stream error without crashing cleanup.

        Application error handlers are optional.
        """

        if self._on_error is not None:
            try:
                self._on_error(exc)
                return
            except Exception:
                traceback.print_exc()

        traceback.print_exception(
            type(exc),
            exc,
            exc.__traceback__,
        )
