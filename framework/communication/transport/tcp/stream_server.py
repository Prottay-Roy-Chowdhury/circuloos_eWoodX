"""Generic bidirectional TCP JSON streaming server."""

import socket
import threading
import uuid
from typing import Any, Callable, Dict
import sys

from framework.communication.transport.tcp.config import (
    DEFAULT_ACCEPT_TIMEOUT,
    DEFAULT_HOST,
)
from framework.communication.transport.tcp.stream_connection import (
    TCPStreamConnection,
)


MessageCallback = Callable[[str, Dict[str, Any]], None]
ConnectCallback = Callable[[str, tuple], None]
DisconnectCallback = Callable[[str], None]


class TCPStreamServer:
    """
    Persistent bidirectional TCP JSON streaming server.

    Supports multiple concurrent clients, targeted messages,
    broadcasts, and controlled startup/shutdown.

    start() confirms that the listening socket is ready
    before returning.
    """

    def __init__(
        self,
        port: int,
        on_message: MessageCallback,
        host: str = DEFAULT_HOST,
        accept_timeout: float = DEFAULT_ACCEPT_TIMEOUT,
        on_connect: ConnectCallback | None = None,
        on_disconnect: DisconnectCallback | None = None,
    ):
        if not callable(on_message):
            raise TypeError("on_message must be callable.")

        self.host = str(host)
        self.port = int(port)
        self.accept_timeout = float(accept_timeout)

        self.on_message = on_message
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        self._connections: Dict[
            str, TCPStreamConnection
        ] = {}

        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._stop_event = threading.Event()

        self._server_socket: socket.socket | None = None
        self._server_thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        """Whether the server listener is active."""

        with self._lifecycle_lock:
            return (
                self._server_socket is not None
                and self._server_thread is not None
                and self._server_thread.is_alive()
                and not self._stop_event.is_set()
            )

    @property
    def client_ids(self) -> list[str]:
        """Return identifiers of connected clients."""

        with self._lock:
            return list(self._connections.keys())

    def start(self) -> None:
        """
        Bind, listen, and start the background accept loop.

        Raises OSError directly if socket setup fails.
        """

        with self._lifecycle_lock:
            if self._server_thread is not None:
                if self._server_thread.is_alive():
                    raise RuntimeError(
                        "Stream server is already running."
                    )

            server = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM,
            )

            try:
                if sys.platform == "win32":
                    # Prevent another socket from binding to the same
                    # listening address and port on Windows.
                    server.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_EXCLUSIVEADDRUSE,
                        1,
                    )
                else:
                    # Allow conventional address reuse after shutdown
                    # on Linux and other supported Unix systems.
                    server.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_REUSEADDR,
                        1,
                    )

                server.bind((self.host, self.port))
                server.listen()
                server.settimeout(self.accept_timeout)

            except Exception:
                server.close()
                raise

            self._stop_event.clear()
            self._server_socket = server

            self._server_thread = threading.Thread(
                target=self._serve,
                args=(server,),
                name="tcp-stream-server",
                daemon=True,
            )

            try:
                self._server_thread.start()
            except Exception:
                self._stop_event.set()
                self._server_socket = None
                self._server_thread = None
                server.close()
                raise

        print(
            f"[tcp-stream-server] Listening on "
            f"{self.host}:{self.port}"
        )

    def _serve(self, server: socket.socket) -> None:
        """Accept clients until shutdown is requested."""

        try:
            while not self._stop_event.is_set():

                try:
                    client_socket, address = server.accept()

                except socket.timeout:
                    continue

                except OSError:
                    if self._stop_event.is_set():
                        break
                    raise

                client_id = str(uuid.uuid4())

                connection = TCPStreamConnection(
                    sock=client_socket,
                    on_message=lambda message, cid=client_id: (
                        self.on_message(cid, message)
                    ),
                    on_disconnect=lambda cid=client_id: (
                        self._handle_disconnect(cid)
                    ),
                )

                # Registration and shutdown must be synchronized.
                # stop() uses the same lifecycle lock when setting
                # the stop event.
                with self._lifecycle_lock:
                    if self._stop_event.is_set():
                        client_socket.close()
                        break

                    with self._lock:
                        self._connections[client_id] = connection

                try:
                    # stop() may close the registered connection
                    # before its receive thread starts.
                    if not connection.connected:
                        break

                    connection.start()

                    if self._stop_event.is_set():
                        connection.close()
                        break

                    if self.on_connect is not None:
                        self.on_connect(client_id, address)

                except Exception:
                    connection.close()

                    # Shutdown-related startup failures are expected.
                    # Other failures must still be reported.
                    if self._stop_event.is_set():
                        break

                    raise

        finally:
            self._stop_event.set()

            try:
                server.close()
            except OSError:
                pass

            with self._lock:
                connections = list(
                    self._connections.values()
                )

            for connection in connections:
                connection.close()

    def send(
        self,
        client_id: str,
        message: Dict[str, Any],
    ) -> None:
        """Send one JSON message to a specific client."""

        with self._lock:
            connection = self._connections.get(client_id)

        if connection is None or not connection.connected:
            raise ConnectionError(
                f"Client is not connected: {client_id}"
            )

        connection.send(message)

    def broadcast(
        self,
        message: Dict[str, Any],
    ) -> None:
        """Send one JSON message to all connected clients."""

        with self._lock:
            connections = list(
                self._connections.values()
            )

        for connection in connections:
            if connection.connected:
                try:
                    connection.send(message)
                except (OSError, ConnectionError):
                    pass

    def _handle_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client and notify the application."""

        with self._lock:
            self._connections.pop(client_id, None)

        if self.on_disconnect is not None:
            self.on_disconnect(client_id)

    def stop(self) -> None:
        """
        Stop the listener and close active client connections.

        The accept thread is joined before returning.
        """

        with self._lifecycle_lock:
            self._stop_event.set()

            server = self._server_socket
            self._server_socket = None

            thread = self._server_thread

            if server is not None:
                try:
                    server.close()
                except OSError:
                    pass

        # Close connections outside the lifecycle lock.
        with self._lock:
            connections = list(
                self._connections.values()
            )

        for connection in connections:
            connection.close()

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(
                timeout=self.accept_timeout + 2.0
            )

            if thread.is_alive():
                raise RuntimeError(
                    "TCP stream server did not stop "
                    "within the expected timeout."
                )

        with self._lifecycle_lock:
            if self._server_thread is thread:
                self._server_thread = None
