"""Low-level TCP file streaming utilities."""

import os
import socket
from pathlib import Path
from typing import Any, Dict, Union

from framework.communication.transport.tcp.config import (
    FILE_CHUNK_SIZE,
)


PathLike = Union[str, Path]


def get_file_info(
    file_path: PathLike,
) -> Dict[str, Any]:
    """
    Return basic metadata required before transferring a file.
    """

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    return {
        "file_name": path.name,
        "file_size": path.stat().st_size,
    }


def send_file(
    sock: socket.socket,
    file_path: PathLike,
    chunk_size: int = FILE_CHUNK_SIZE,
) -> int:
    """
    Stream one file through an already-connected TCP socket.

    No JSON metadata is sent here. The caller is responsible for
    negotiating the file name and expected size before calling this
    function.

    Returns the number of bytes sent.
    """

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    sent_size = 0

    with path.open("rb") as file:

        while True:

            chunk = file.read(
                chunk_size
            )

            if not chunk:
                break

            sock.sendall(
                chunk
            )

            sent_size += len(
                chunk
            )

    return sent_size


def receive_file(
    sock: socket.socket,
    destination: PathLike,
    expected_size: int,
    chunk_size: int = FILE_CHUNK_SIZE,
) -> int:
    """
    Receive exactly `expected_size` raw bytes from a TCP socket.

    The file is first written to a temporary '.receiving' file and
    atomically moved into place only after the complete byte count has
    been received.

    Returns the number of bytes received.
    """

    if expected_size < 0:
        raise ValueError(
            "expected_size cannot be negative."
        )

    destination = Path(
        destination
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        destination.with_suffix(
            destination.suffix + ".receiving"
        )
    )

    received_size = 0

    try:

        with temporary_path.open(
            "wb"
        ) as file:

            while received_size < expected_size:

                remaining = (
                    expected_size
                    - received_size
                )

                chunk = sock.recv(
                    min(
                        chunk_size,
                        remaining,
                    )
                )

                if not chunk:
                    raise ConnectionError(
                        "Connection closed during "
                        f"transfer of {destination.name}."
                    )

                file.write(
                    chunk
                )

                received_size += len(
                    chunk
                )

        if received_size != expected_size:
            raise IOError(
                f"Incorrect file size for "
                f"{destination.name}: "
                f"expected {expected_size}, "
                f"received {received_size}."
            )

        os.replace(
            temporary_path,
            destination,
        )

    except Exception:

        if temporary_path.exists():
            temporary_path.unlink()

        raise

    return received_size