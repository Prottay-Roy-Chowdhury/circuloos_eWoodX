"""TCP client for negotiated file transfers."""

import socket
from pathlib import Path
from typing import Any, Dict, Union

from framework.communication.transport.tcp.config import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_HOST,
)
from framework.communication.transport.tcp.file_transfer import (
    get_file_info,
    receive_file,
    send_file,
)
from framework.communication.transport.tcp.protocol import (
    receive_message,
    send_message,
)


PathLike = Union[str, Path]


class TCPFileClient:
    """
    Client for downloading and uploading files over TCP.

    JSON messages are used for transfer negotiation.
    File contents are streamed as raw bytes.
    """

    def __init__(
        self,
        port: int,
        host: str = DEFAULT_HOST,        
        timeout: float = DEFAULT_CONNECT_TIMEOUT,
    ):
        self.host = str(host)
        self.port = int(port)
        self.timeout = float(timeout)

    def download(
        self,
        request: Dict[str, Any],
        destination: PathLike,
    ) -> Dict[str, Any]:
        """
        Request one file from a server and save it locally.

        Expected server response:

            {
                "status": "ok",
                "file_name": "...",
                "file_size": ...
            }

        followed immediately by the raw file bytes.
        """

        if not isinstance(request, dict):
            raise TypeError(
                "request must be a dictionary."
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
                request,
            )

            response = receive_message(
                sock
            )

            if response.get("status") != "ok":
                return response

            file_size = int(
                response["file_size"]
            )

            receive_file(
                sock=sock,
                destination=destination,
                expected_size=file_size,
            )

        return response

    def upload(
        self,
        request: Dict[str, Any],
        file_path: PathLike,
    ) -> Dict[str, Any]:
        """
        Upload one file to a server.

        The method adds file metadata to the supplied request.

        Protocol:

            request metadata
                ↓
            server ready response
                ↓
            raw file bytes
                ↓
            completion response
        """

        if not isinstance(request, dict):
            raise TypeError(
                "request must be a dictionary."
            )

        file_info = get_file_info(
            file_path
        )

        transfer_request = dict(
            request
        )

        transfer_request.update(
            file_info
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
                transfer_request,
            )

            ready_response = receive_message(
                sock
            )

            if (
                ready_response.get("status")
                != "ok"
            ):
                return ready_response

            send_file(
                sock=sock,
                file_path=file_path,
            )

            completion_response = (
                receive_message(
                    sock
                )
            )

        return completion_response