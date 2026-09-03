"""TCP JSON message framing for the communication framework.

Wire format:

    [fixed-size length header][UTF-8 JSON payload]

This keeps the same basic communication contract already tested in DECO2,
while removing project-specific configuration dependencies.
"""

import json
import socket
from typing import Any, Dict
from framework.communication.transport.tcp.config import DEFAULT_HEADER_SIZE



def encode_message(
    message: Dict[str, Any],
    header_size: int = DEFAULT_HEADER_SIZE,
) -> bytes:
    """
    Serialize a dictionary into a framed JSON message.

    Frame structure:
        header  -> payload length encoded as big-endian integer
        payload -> UTF-8 encoded JSON
    """

    payload = json.dumps(message).encode("utf-8")

    header = len(payload).to_bytes(
        header_size,
        byteorder="big",
    )

    return header + payload


def recv_exact(
    sock: socket.socket,
    size: int,
) -> bytes:
    """
    Receive exactly `size` bytes from the socket.

    Raises ConnectionError if the remote side closes the connection
    before all requested bytes are received.
    """

    data = b""

    while len(data) < size:
        packet = sock.recv(
            size - len(data)
        )

        if not packet:
            raise ConnectionError(
                "Socket connection closed."
            )

        data += packet

    return data


def receive_message(
    sock: socket.socket,
    header_size: int = DEFAULT_HEADER_SIZE,
) -> Dict[str, Any]:
    """
    Receive and decode one framed JSON message.
    """

    header = recv_exact(
        sock,
        header_size,
    )

    payload_size = int.from_bytes(
        header,
        byteorder="big",
    )

    payload = recv_exact(
        sock,
        payload_size,
    )

    return json.loads(
        payload.decode("utf-8")
    )


def send_message(
    sock: socket.socket,
    message: Dict[str, Any],
    header_size: int = DEFAULT_HEADER_SIZE,
) -> None:
    """
    Send one framed JSON message.
    """

    encoded = encode_message(
        message,
        header_size=header_size,
    )

    sock.sendall(encoded)


def ok_response(
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Build a standard successful response.
    """

    response: Dict[str, Any] = {
        "status": "ok"
    }

    response.update(kwargs)

    return response


def error_response(
    message: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Build a standard error response.
    """

    response: Dict[str, Any] = {
        "status": "error",
        "message": message,
    }

    response.update(kwargs)

    return response