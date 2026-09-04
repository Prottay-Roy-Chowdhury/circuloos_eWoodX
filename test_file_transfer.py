import threading
import time
from pathlib import Path

from framework.communication.transport.tcp import (
    TCPFileClient,
    TCPFileServer,
)


HOST = "127.0.0.1"
PORT = 5006

TEST_DIR = Path("test_file_transfer_data")

SERVER_FILES = TEST_DIR / "server"
CLIENT_FILES = TEST_DIR / "client"

SERVER_FILES.mkdir(
    parents=True,
    exist_ok=True,
)

CLIENT_FILES.mkdir(
    parents=True,
    exist_ok=True,
)


def resolve_download(request):
    """
    Resolve a requested file on the server.
    """

    file_name = request["file_name"]

    return SERVER_FILES / file_name


def resolve_upload(request):
    """
    Decide where an uploaded file should be stored.
    """

    file_name = request["file_name"]

    return SERVER_FILES / (
        "uploaded_" + file_name
    )


# --------------------------------------------------
# Prepare source file for download test
# --------------------------------------------------

download_source = (
    SERVER_FILES / "download_test.txt"
)

download_source.write_text(
    "Hello from TCP file server.",
    encoding="utf-8",
)


# --------------------------------------------------
# Start server
# --------------------------------------------------

server = TCPFileServer(
    port=PORT,
    host=HOST,
    download_resolver=resolve_download,
    upload_resolver=resolve_upload,
)


server_thread = threading.Thread(
    target=server.start,
    daemon=True,
)

server_thread.start()

time.sleep(0.5)


# --------------------------------------------------
# Create client
# --------------------------------------------------

client = TCPFileClient(
    port=PORT,
    host=HOST,
)


# --------------------------------------------------
# DOWNLOAD TEST
# --------------------------------------------------

download_destination = (
    CLIENT_FILES / "downloaded.txt"
)

download_response = client.download(
    request={
        "operation": "download",
        "file_name": "download_test.txt",
    },
    destination=download_destination,
)


print(
    "[download] response:",
    download_response,
)


assert (
    download_destination.read_bytes()
    == download_source.read_bytes()
)

print(
    "[download] file contents verified"
)


# --------------------------------------------------
# UPLOAD TEST
# --------------------------------------------------

upload_source = (
    CLIENT_FILES / "upload_test.txt"
)

upload_source.write_text(
    "Hello from TCP file client.",
    encoding="utf-8",
)


upload_response = client.upload(
    request={
        "operation": "upload",
    },
    file_path=upload_source,
)


print(
    "[upload] response:",
    upload_response,
)


uploaded_destination = (
    SERVER_FILES / "uploaded_upload_test.txt"
)


assert (
    uploaded_destination.read_bytes()
    == upload_source.read_bytes()
)

print(
    "[upload] file contents verified"
)


# --------------------------------------------------
# Stop server
# --------------------------------------------------

server.stop()

server_thread.join(
    timeout=2.0
)


print(
    "[test] TCP file transfer passed"
)