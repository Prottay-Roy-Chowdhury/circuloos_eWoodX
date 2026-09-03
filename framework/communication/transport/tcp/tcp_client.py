"""Generic TCP JSON client."""

import socket
from typing import Any, Dict

from framework.communication.transport.tcp.config import (
    DEFAULT_COMMAND_PORT,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_HOST,
)
from framework.communication.transport.tcp.protocol import (
    receive_message,
    send_message,
)


class TCPClient:
    """
    Simple request-response TCP client.

    Each request opens one TCP connection:

        connect
          ↓
        send JSON message
          ↓
        receive JSON response
          ↓
        close

    This preserves the communication pattern already tested
    in the DECO2 agent system.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_COMMAND_PORT,
        timeout: float = DEFAULT_CONNECT_TIMEOUT,
    ):
        self.host = str(host)
        self.port = int(port)
        self.timeout = float(timeout)

    def send(
        self,
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send one request and wait for one response.
        """

        if not isinstance(message, dict):
            raise TypeError(
                "message must be a dictionary."
            )

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as sock:

            sock.settimeout(
                self.timeout
            )

            sock.connect(
                (
                    self.host,
                    self.port,
                )
            )

            send_message(
                sock,
                message,
            )

            response = receive_message(
                sock
            )

        return response