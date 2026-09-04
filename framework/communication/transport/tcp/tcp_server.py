"""Generic TCP JSON request-response server."""

import socket
import traceback
from typing import Any, Callable, Dict

from framework.communication.transport.tcp.config import (
    DEFAULT_ACCEPT_TIMEOUT,    
    DEFAULT_HOST,
)
from framework.communication.transport.tcp.protocol import (
    error_response,
    receive_message,
    send_message,
)


MessageHandler = Callable[
    [Dict[str, Any]],
    Dict[str, Any],
]


class TCPServer:
    """
    Generic TCP JSON request-response server.

    The server owns socket communication only.

    Application behavior is provided through a message handler:

        TCP request
            ↓
        receive JSON
            ↓
        handler(message)
            ↓
        response dictionary
            ↓
        send JSON
    """

    def __init__(
        self,        
        handler: MessageHandler,
        port: int,
        host: str = DEFAULT_HOST,        
        accept_timeout: float = DEFAULT_ACCEPT_TIMEOUT,
    ):
        if not callable(handler):
            raise TypeError(
                "handler must be callable."
            )

        self.handler = handler
        self.host = str(host)
        self.port = int(port)

        self.accept_timeout = float(
            accept_timeout
        )

        self.running = False

    def start(self) -> None:
        """
        Start the blocking server loop.
        """

        self.running = True

        print(
            f"[tcp-server] Listening on "
            f"{self.host}:{self.port}"
        )

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as server:

            server.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1,
            )

            server.bind(
                (
                    self.host,
                    self.port,
                )
            )

            server.listen()

            server.settimeout(
                self.accept_timeout
            )

            try:

                while self.running:

                    try:
                        client, address = (
                            server.accept()
                        )

                    except socket.timeout:
                        continue

                    with client:

                        print(
                            "[tcp-server] Connected: "
                            f"{address}"
                        )

                        response = (
                            self._handle_client(
                                client
                            )
                        )

                        send_message(
                            client,
                            response,
                        )

            except KeyboardInterrupt:

                print(
                    "\n[tcp-server] "
                    "Stopping."
                )

            finally:

                self.running = False

    def stop(self) -> None:
        """
        Request the server loop to stop.

        Because accept() uses a timeout, the loop will observe
        this flag without blocking indefinitely.
        """

        self.running = False

    def _handle_client(
        self,
        client: socket.socket,
    ) -> Dict[str, Any]:
        """
        Receive one message and pass it to the application handler.
        """

        try:

            message = receive_message(
                client
            )

            response = self.handler(
                message
            )

            if not isinstance(
                response,
                dict,
            ):
                raise TypeError(
                    "Message handler must return "
                    "a dictionary."
                )

            return response

        except Exception as exc:

            traceback.print_exc()

            return error_response(
                str(exc)
            )