import threading
import time
from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)

from framework.communication.transport.tcp import (
    TCPClient,
    TCPServer,
    ok_response,
)


def handle_message(message):
    print(
        "[handler] received:",
        message,
    )

    command = message.get(
        "command"
    )

    if command == "ping":
        return ok_response(
            message="pong"
        )

    return ok_response(
        echo=message
    )


server = TCPServer(
    handler=handle_message,
    host="127.0.0.1",
    port=5005,
)


server_thread = threading.Thread(
    target=server.start,
    daemon=True,
)

server_thread.start()


time.sleep(0.5)


client = TCPClient(
    host="127.0.0.1",
    port=5005,
)


response = client.send(
    {
        "command": "ping"
    }
)


print(
    "[client] response:",
    response,
)


server.stop()