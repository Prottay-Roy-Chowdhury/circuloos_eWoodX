"""Generic bidirectional TCP JSON streaming server."""

import socket
import threading
import uuid
from typing import Any, Callable, Dict

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

    Supports multiple concurrent client connections.

    Each client has an independent receive thread.
    Messages can be sent to one client or broadcast
    to all connected clients.
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
        self._stop_event = threading.Event()

        self._server_socket: socket.socket | None = None
        self._server_thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        """Whether the server is accepting connections."""

        return (
            self._server_thread is not None
            and self._server_thread.is_alive()
            and not self._stop_event.is_set()
        )

    @property
    def client_ids(self) -> list[str]:
        """Return identifiers of currently connected clients."""

        with self._lock:
            return list(self._connections.keys())

    def start(self) -> None:
        """Start the TCP listener in a background thread."""

        with self._lock:
            if self.running:
                raise RuntimeError("Stream server is already running.")

            self._stop_event.clear()

            self._server_thread = threading.Thread(
                target=self._serve,
                name="tcp-stream-server",
                daemon=True,
            )

            self._server_thread.start()

    def _serve(self) -> None:
        """Accept clients and create independent stream connections."""

        server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        try:
            server.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1,
            )

            server.bind((self.host, self.port))
            server.listen()
            server.settimeout(self.accept_timeout)

            self._server_socket = server

            print(
                f"[tcp-stream-server] Listening on "
                f"{self.host}:{self.port}"
            )

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

                with self._lock:
                    self._connections[client_id] = connection

                try:
                    connection.start()

                    if self.on_connect is not None:
                        self.on_connect(client_id, address)

                except Exception:
                    connection.close()
                    raise

        finally:
            self._stop_event.set()

            try:
                server.close()
            except OSError:
                pass

            with self._lock:
                connections = list(self._connections.values())

            for connection in connections:
                connection.close()

            self._server_socket = None

    def send(
        self,
        client_id: str,
        message: Dict[str, Any],
    ) -> None:
        """Send one JSON message to a specific connected client."""

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
        """Send one JSON message to every connected client."""

        with self._lock:
            connections = list(self._connections.values())

        for connection in connections:
            if connection.connected:
                try:
                    connection.send(message)
                except (OSError, ConnectionError):
                    # A disconnected client should not prevent
                    # delivery to other connected clients.
                    pass

    def _handle_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client and notify the application."""

        with self._lock:
            self._connections.pop(client_id, None)

        if self.on_disconnect is not None:
            self.on_disconnect(client_id)

    def stop(self) -> None:
        """Stop accepting clients and close active connections."""

        self._stop_event.set()

        server = self._server_socket

        if server is not None:
            try:
                server.close()
            except OSError:
                pass

        with self._lock:
            connections = list(self._connections.values())

        for connection in connections:
            connection.close()

        thread = self._server_thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=self.accept_timeout + 1.0)
