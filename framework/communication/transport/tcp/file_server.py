"""Generic TCP file-transfer server."""

import socket
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from framework.communication.transport.tcp.config import (
    DEFAULT_ACCEPT_TIMEOUT,
    DEFAULT_HOST,
)
from framework.communication.transport.tcp.file_transfer import (
    get_file_info,
    receive_file,
    send_file,
)
from framework.communication.transport.tcp.protocol import (
    error_response,
    ok_response,
    receive_message,
    send_message,
)


PathLike = Union[str, Path]

DownloadResolver = Callable[
    [Dict[str, Any]],
    PathLike,
]

UploadResolver = Callable[
    [Dict[str, Any]],
    PathLike,
]


class TCPFileServer:
    """
    Generic TCP server for negotiated file transfers.

    The server owns transport mechanics only.

    File selection and destination paths are provided by
    application-level resolver functions.
    """

    def __init__(
        self,
        port: int,
        download_resolver: Optional[
            DownloadResolver
        ] = None,
        upload_resolver: Optional[
            UploadResolver
        ] = None,
        host: str = DEFAULT_HOST,
        accept_timeout: float = DEFAULT_ACCEPT_TIMEOUT,
    ):
        self.download_resolver = (
            download_resolver
        )

        self.upload_resolver = (
            upload_resolver
        )

        self.host = str(host)
        self.port = int(port)

        self.accept_timeout = float(
            accept_timeout
        )

        self.running = False

    def start(self) -> None:
        """
        Start the blocking file-transfer server.
        """

        self.running = True

        print(
            f"[tcp-file-server] Listening on "
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
                            "[tcp-file-server] "
                            f"Connected: {address}"
                        )

                        try:

                            self._handle_client(
                                client
                            )

                        except Exception as exc:

                            traceback.print_exc()

                            try:

                                send_message(
                                    client,
                                    error_response(
                                        str(exc)
                                    ),
                                )

                            except Exception:
                                pass

            except KeyboardInterrupt:

                print(
                    "\n[tcp-file-server] "
                    "Stopping."
                )

            finally:

                self.running = False

    def stop(self) -> None:
        """
        Request the server loop to stop.
        """

        self.running = False

    def _handle_client(
        self,
        client: socket.socket,
    ) -> None:
        """
        Receive one transfer request and dispatch it.
        """

        request = receive_message(
            client
        )

        operation = request.get(
            "operation"
        )

        if operation == "download":

            self._handle_download(
                client,
                request,
            )

            return

        if operation == "upload":

            self._handle_upload(
                client,
                request,
            )

            return

        send_message(
            client,
            error_response(
                "Unsupported file transfer operation."
            ),
        )

    def _handle_download(
        self,
        client: socket.socket,
        request: Dict[str, Any],
    ) -> None:

        if self.download_resolver is None:

            send_message(
                client,
                error_response(
                    "Downloads are not supported."
                ),
            )

            return

        file_path = Path(
            self.download_resolver(
                request
            )
        )

        file_info = get_file_info(
            file_path
        )

        send_message(
            client,
            ok_response(
                **file_info
            ),
        )

        send_file(
            sock=client,
            file_path=file_path,
        )

    def _handle_upload(
        self,
        client: socket.socket,
        request: Dict[str, Any],
    ) -> None:

        if self.upload_resolver is None:

            send_message(
                client,
                error_response(
                    "Uploads are not supported."
                ),
            )

            return

        if "file_size" not in request:

            send_message(
                client,
                error_response(
                    "Missing file_size."
                ),
            )

            return

        expected_size = int(
            request["file_size"]
        )

        destination = Path(
            self.upload_resolver(
                request
            )
        )

        send_message(
            client,
            ok_response(
                message="Ready to receive file."
            ),
        )

        received_size = receive_file(
            sock=client,
            destination=destination,
            expected_size=expected_size,
        )

        send_message(
            client,
            ok_response(
                message="File received.",
                file_name=destination.name,
                file_size=received_size,
            ),
        )