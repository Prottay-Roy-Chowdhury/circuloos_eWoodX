# TCP Transport

The `framework.communication.transport.tcp` package provides generic TCP-based communication for the framework.

It supports two related transport patterns:

1. **JSON request-response communication** for structured messages.
2. **Negotiated file transfer** using JSON messages for coordination and raw TCP bytes for file contents.

The package is independent of application-specific commands, actions, entities, files, and storage structures.

The public API is:

```python
from framework.communication.transport.tcp import (
    encode_message,
    receive_message,
    send_message,
    ok_response,
    error_response,
    TCPClient,
    TCPServer,
    get_file_info,
    send_file,
    receive_file,
    TCPFileClient,
    TCPFileServer,
    TCPStreamClient,
    TCPStreamServer,
)
```

## Responsibility

The TCP transport layer provides:

- framing and serialization of JSON messages;
- reliable reception of complete framed messages;
- standard success and error response dictionaries;
- request-response TCP clients and servers;
- low-level binary file streaming;
- negotiated file download and upload;
- separation between transport mechanics and application-level file resolution.

It does **not**:

- interpret application commands;
- define action lifecycle behavior;
- persist actions;
- determine which agent should execute work;
- decide which application file a semantic request refers to;
- define application-specific file destinations;
- execute application operations.

Application behavior is supplied to the transport layer through handlers and resolver functions.

---

# JSON Message Protocol

Structured TCP messages use a length-prefixed JSON protocol.

The wire format is:

```text
┌──────────────────────────┬─────────────────────────────┐
│ fixed-size length header │ UTF-8 JSON payload          │
└──────────────────────────┴─────────────────────────────┘
```

The header contains the number of bytes in the JSON payload encoded as a big-endian integer.

Conceptually:

```text
Python dictionary
       ↓
JSON serialization
       ↓
UTF-8 bytes
       ↓
payload length
       ↓
[length header][JSON payload]
```

The receiver first reads the complete fixed-size header, determines the payload size, and then reads exactly that number of payload bytes.

This framing allows the receiver to distinguish message boundaries independently of how TCP divides the transmitted data into packets.

---

# `encode_message()`

```python
encode_message(
    message: dict,
    header_size: int = DEFAULT_HEADER_SIZE,
) -> bytes
```

Serializes a dictionary into the TCP JSON message format.

Example:

```python
from framework.communication.transport.tcp import (
    encode_message,
)

encoded = encode_message(
    {
        "command": "ping",
    }
)
```

The result contains:

```text
[length header][UTF-8 JSON payload]
```

The payload length is encoded as a big-endian integer using `header_size` bytes.

`encode_message()` only creates the byte representation. It does not send anything over a socket.

---

# `send_message()`

```python
send_message(
    sock: socket.socket,
    message: dict,
    header_size: int = DEFAULT_HEADER_SIZE,
) -> None
```

Encodes and sends one framed JSON message through an already-connected socket.

Example:

```python
send_message(
    sock,
    {
        "command": "ping",
    },
)
```

Internally:

```text
dictionary
    ↓
encode_message()
    ↓
socket.sendall()
```

The function does not open or close the socket.

---

# `receive_message()`

```python
receive_message(
    sock: socket.socket,
    header_size: int = DEFAULT_HEADER_SIZE,
) -> dict
```

Receives and decodes one framed JSON message from an already-connected socket.

The sequence is:

```text
receive fixed-size header
          ↓
decode payload size
          ↓
receive exactly payload_size bytes
          ↓
UTF-8 decode
          ↓
JSON decode
          ↓
dictionary
```

If the connection closes before all required bytes are received, a `ConnectionError` is raised.

---

# Standard Responses

The transport package provides helpers for constructing consistent response dictionaries.

## `ok_response()`

```python
ok_response(
    **kwargs,
) -> dict
```

Creates a successful response.

Example:

```python
from framework.communication.transport.tcp import (
    ok_response,
)

response = ok_response(
    message="pong",
)
```

Result:

```python
{
    "status": "ok",
    "message": "pong",
}
```

Additional keyword arguments are added directly to the response.

For example:

```python
ok_response(
    action_id="action-001",
    accepted=True,
)
```

produces:

```python
{
    "status": "ok",
    "action_id": "action-001",
    "accepted": True,
}
```

---

## `error_response()`

```python
error_response(
    message: str,
    **kwargs,
) -> dict
```

Creates a standard error response.

Example:

```python
from framework.communication.transport.tcp import (
    error_response,
)

response = error_response(
    "Unsupported command."
)
```

Result:

```python
{
    "status": "error",
    "message": "Unsupported command.",
}
```

Additional values can also be included through keyword arguments.

---

# TCPClient

```python
class TCPClient
```

`TCPClient` provides a simple JSON request-response client.

Each call to `send()` creates a new TCP connection:

```text
open connection
      ↓
send one JSON request
      ↓
receive one JSON response
      ↓
close connection
```

The client does not maintain a persistent socket between requests.

## Constructor

```python
TCPClient(
    port: int,
    host: str = DEFAULT_HOST,
    timeout: float = DEFAULT_CONNECT_TIMEOUT,
)
```

Example:

```python
from framework.communication.transport.tcp import (
    TCPClient,
)

client = TCPClient(
    host="127.0.0.1",
    port=5005,
)
```

---

## Public attributes

### `host`

```python
client.host: str
```

Hostname or IP address of the TCP server.

### `port`

```python
client.port: int
```

TCP port used for the connection.

### `timeout`

```python
client.timeout: float
```

Socket timeout used by the client.

---

## `send()`

```python
client.send(
    message: dict,
) -> dict
```

Sends one request and waits for one response.

Example:

```python
response = client.send(
    {
        "command": "ping",
    }
)
```

The supplied message must be a dictionary.

The method:

```text
creates socket
     ↓
sets timeout
     ↓
connects
     ↓
send_message()
     ↓
receive_message()
     ↓
closes socket
     ↓
returns response dictionary
```

A new socket is created for every call.

---

# TCPServer

```python
class TCPServer
```

`TCPServer` provides a generic JSON request-response server.

The server owns the TCP communication mechanics while application behavior is delegated to a callable handler.

The relationship is:

```text
TCP client
    ↓
JSON request
    ↓
TCPServer
    ↓
handler(message)
    ↓
response dictionary
    ↓
TCPServer
    ↓
JSON response
```

## Handler contract

A server handler must be callable and accept one dictionary:

```python
def handler(message: dict) -> dict:
    ...
```

It must return a dictionary.

Example:

```python
from framework.communication.transport.tcp import (
    ok_response,
)

def handle_message(message):
    if message.get("command") == "ping":
        return ok_response(
            message="pong",
        )

    return ok_response(
        echo=message,
    )
```

The TCP layer does not interpret the contents of the request.

---

## Constructor

```python
TCPServer(
    handler,
    port: int,
    host: str = DEFAULT_HOST,
    accept_timeout: float = DEFAULT_ACCEPT_TIMEOUT,
)
```

Example:

```python
from framework.communication.transport.tcp import (
    TCPServer,
)

server = TCPServer(
    handler=handle_message,
    host="127.0.0.1",
    port=5005,
)
```

The handler must be callable.

---

## Public attributes

The server exposes:

```python
server.handler
server.host
server.port
server.accept_timeout
server.running
```

`running` represents whether the server loop should continue accepting connections.

---

## `start()`

```python
server.start() -> None
```

Starts the blocking server loop.

The server:

```text
creates TCP socket
      ↓
binds host + port
      ↓
listens
      ↓
accepts connection
      ↓
receives one request
      ↓
calls handler
      ↓
sends one response
      ↓
closes client connection
      ↓
waits for next connection
```

`start()` is blocking.

If the surrounding application needs to continue doing other work, the server can be run in another thread.

Example:

```python
import threading

thread = threading.Thread(
    target=server.start,
    daemon=True,
)

thread.start()
```

The current server handles accepted client connections sequentially within the server loop.

---

## `stop()`

```python
server.stop() -> None
```

Requests the server loop to stop by setting:

```python
server.running = False
```

The listening socket uses an accept timeout, allowing the loop to periodically observe the updated flag instead of blocking indefinitely in `accept()`.

Example:

```python
server.stop()
```

---

## Handler errors

Exceptions raised while receiving or handling a normal JSON request are converted into a standard error response:

```python
{
    "status": "error",
    "message": "...",
}
```

The traceback is also printed by the server.

This keeps transport-level request handling from requiring each application handler to implement its own socket error response mechanism.

---

# Basic Request-Response Example

Server:

```python
from framework.communication.transport.tcp import (
    TCPServer,
    ok_response,
)

def handle_message(message):
    if message.get("command") == "ping":
        return ok_response(
            message="pong",
        )

    return ok_response(
        echo=message,
    )

server = TCPServer(
    handler=handle_message,
    host="127.0.0.1",
    port=5005,
)

server.start()
```

Client:

```python
from framework.communication.transport.tcp import (
    TCPClient,
)

client = TCPClient(
    host="127.0.0.1",
    port=5005,
)

response = client.send(
    {
        "command": "ping",
    }
)

print(response)
```

Expected response:

```python
{
    "status": "ok",
    "message": "pong",
}
```

---

# File Transfer

The TCP package also supports transferring complete files.

File transfer deliberately separates:

```text
transfer negotiation
        │
        └── framed JSON messages

file contents
        │
        └── raw TCP bytes
```

This avoids encoding binary files into JSON.

The file-transfer components are:

```python
get_file_info
send_file
receive_file
TCPFileClient
TCPFileServer
```

---

# `get_file_info()`

```python
get_file_info(
    file_path: str | Path,
) -> dict
```

Returns the basic metadata required for transferring a file.

Example:

```python
from framework.communication.transport.tcp import (
    get_file_info,
)

info = get_file_info(
    "data/example.bin"
)
```

Result:

```python
{
    "file_name": "example.bin",
    "file_size": 12345,
}
```

If the path does not identify an existing file, `FileNotFoundError` is raised.

---

# `send_file()`

```python
send_file(
    sock: socket.socket,
    file_path: str | Path,
    chunk_size: int = FILE_CHUNK_SIZE,
) -> int
```

Streams a file through an already-connected TCP socket.

The file is read in chunks and sent using:

```python
sock.sendall(...)
```

The method returns the total number of bytes sent.

Example:

```python
sent_size = send_file(
    sock=socket_connection,
    file_path="data/example.bin",
)
```

`send_file()` sends **only the raw file contents**.

It does not send:

- the file name;
- the file size;
- JSON metadata;
- transfer commands.

The caller is responsible for negotiating those values before raw byte streaming begins.

---

# `receive_file()`

```python
receive_file(
    sock: socket.socket,
    destination: str | Path,
    expected_size: int,
    chunk_size: int = FILE_CHUNK_SIZE,
) -> int
```

Receives exactly `expected_size` raw bytes and stores them at the requested destination.

The destination's parent directories are created automatically when required.

## Temporary file behavior

The received data is first written to:

```text
<destination>.receiving
```

Only after the complete expected byte count has been received is the temporary file moved into place:

```text
file.ext.receiving
       ↓ complete transfer
file.ext
```

If transfer fails, the temporary file is removed.

This prevents an incomplete transfer from appearing at the final destination as though it were complete.

The method returns the number of bytes received.

A negative `expected_size` is rejected.

If the connection closes before the expected byte count is received, `ConnectionError` is raised.

---

# TCPFileClient

```python
class TCPFileClient
```

`TCPFileClient` provides negotiated file download and upload over TCP.

JSON messages describe and coordinate the transfer. File contents are transmitted as raw bytes.

## Constructor

```python
TCPFileClient(
    port: int,
    host: str = DEFAULT_HOST,
    timeout: float = DEFAULT_CONNECT_TIMEOUT,
)
```

Example:

```python
from framework.communication.transport.tcp import (
    TCPFileClient,
)

client = TCPFileClient(
    host="127.0.0.1",
    port=5006,
)
```

---

## Public attributes

```python
client.host
client.port
client.timeout
```

These have the same roles as the corresponding `TCPClient` attributes.

---

## `download()`

```python
client.download(
    request: dict,
    destination: str | Path,
) -> dict
```

Requests one file and saves it to a local destination.

The request dictionary is application-defined, but it must provide whatever information the server-side download resolver requires.

A simple example could be:

```python
response = client.download(
    request={
        "operation": "download",
        "file_name": "result.json",
    },
    destination="downloads/result.json",
)
```

The protocol is:

```text
CLIENT                              SERVER

JSON request
   ───────────────────────────────►

                          resolve requested file
                                   │
                                   ▼

                 JSON response:
                 status
                 file_name
                 file_size
   ◄───────────────────────────────

raw file bytes
   ◄───────────────────────────────

save destination
```

A successful negotiation response has the form:

```python
{
    "status": "ok",
    "file_name": "result.json",
    "file_size": 12345,
}
```

The client then receives exactly `file_size` bytes.

If the server returns a response whose status is not `"ok"`, the response is returned immediately and no file is received.

---

## `upload()`

```python
client.upload(
    request: dict,
    file_path: str | Path,
) -> dict
```

Uploads one local file.

The client automatically obtains:

```python
{
    "file_name": ...,
    "file_size": ...,
}
```

from the supplied file and adds those values to a copy of the request.

The original request dictionary is not modified.

Example:

```python
response = client.upload(
    request={
        "operation": "upload",
    },
    file_path="data/result.json",
)
```

The protocol is:

```text
CLIENT                              SERVER

JSON request
+ file_name
+ file_size
   ───────────────────────────────►

                     resolve destination

                 JSON ready response
   ◄───────────────────────────────

raw file bytes
   ───────────────────────────────►

                     receive complete file

                 JSON completion response
   ◄───────────────────────────────
```

If the server rejects the initial request, no file contents are sent.

---

# TCPFileServer

```python
class TCPFileServer
```

`TCPFileServer` provides generic negotiated file transfer.

A central design principle is:

> The transport server moves bytes, while application-level resolvers decide which files those bytes represent.

The server therefore does not contain application-specific filesystem logic.

Instead, it accepts resolver functions.

---

# Resolver Functions

Two independent resolver types are supported:

```text
DownloadResolver
UploadResolver
```

Both receive the complete request dictionary and return a filesystem path.

## Download resolver

```python
def resolve_download(
    request: dict,
) -> str | Path:
    ...
```

The resolver determines which existing server-side file should be sent.

Example:

```python
def resolve_download(request):
    file_name = request["file_name"]

    return SERVER_FILES / file_name
```

The server then validates the returned path as a file and streams it.

---

## Upload resolver

```python
def resolve_upload(
    request: dict,
) -> str | Path:
    ...
```

The resolver determines where the uploaded file should be stored.

Example:

```python
def resolve_upload(request):
    file_name = request["file_name"]

    return SERVER_FILES / (
        "uploaded_" + file_name
    )
```

Resolvers may use any semantic information supplied in the request.

Therefore a higher application layer can resolve requests such as:

```python
{
    "operation": "download",
    "resource_id": "resource-001",
    "file": "result.json",
}
```

without exposing server-local paths to the client.

The TCP framework itself does not define those semantics.

---

# TCPFileServer Constructor

```python
TCPFileServer(
    port: int,
    download_resolver=None,
    upload_resolver=None,
    host: str = DEFAULT_HOST,
    accept_timeout: float = DEFAULT_ACCEPT_TIMEOUT,
)
```

Either resolver can be omitted.

For example, a download-only server can be created with:

```python
server = TCPFileServer(
    host="127.0.0.1",
    port=5006,
    download_resolver=resolve_download,
)
```

If no download resolver is configured, download requests receive:

```python
{
    "status": "error",
    "message": "Downloads are not supported.",
}
```

If no upload resolver is configured, upload requests receive the corresponding upload error.

---

## Public attributes

The server exposes:

```python
server.download_resolver
server.upload_resolver
server.host
server.port
server.accept_timeout
server.running
```

---

## `start()`

```python
server.start() -> None
```

Starts the blocking file-transfer server.

Each accepted connection carries one transfer request.

The request must contain an operation:

```python
{
    "operation": "download",
    ...
}
```

or:

```python
{
    "operation": "upload",
    ...
}
```

Unsupported operations receive an error response.

As with `TCPServer`, the file server can be run in a daemon thread when the surrounding process must provide other services simultaneously.

---

## `stop()`

```python
server.stop() -> None
```

Requests the server loop to stop.

The server's accept timeout allows the loop to observe the updated `running` flag.

---

# Download Flow

A complete download follows this sequence:

```text
TCPFileClient
      │
      │ JSON download request
      ▼
TCPFileServer
      │
      ▼
download_resolver(request)
      │
      ▼
server-side Path
      │
      ▼
get_file_info()
      │
      │ JSON:
      │ status=ok
      │ file_name
      │ file_size
      ▼
TCPFileClient
      │
      │ raw bytes
      ▼
receive_file()
      │
      ▼
local destination
```

The resolver owns **file selection**.

The TCP transport owns **file transfer**.

---

# Upload Flow

A complete upload follows:

```text
local file
    │
    ▼
get_file_info()
    │
    ▼
request + file_name + file_size
    │
    ▼
TCPFileServer
    │
    ▼
upload_resolver(request)
    │
    ▼
destination Path
    │
    │ ready response
    ▼
TCPFileClient
    │
    │ raw bytes
    ▼
TCPFileServer
    │
    ▼
receive_file()
    │
    ▼
destination
    │
    │ completion response
    ▼
TCPFileClient
```

Again, the resolver decides **where the file belongs**, while the transport handles **how its bytes move**.

---

# Complete File-Transfer Example

```python
from pathlib import Path
import threading

from framework.communication.transport.tcp import (
    TCPFileClient,
    TCPFileServer,
)

SERVER_FILES = Path("server_files")


def resolve_download(request):
    return (
        SERVER_FILES
        / request["file_name"]
    )


def resolve_upload(request):
    return (
        SERVER_FILES
        / ("uploaded_" + request["file_name"])
    )


server = TCPFileServer(
    host="127.0.0.1",
    port=5006,
    download_resolver=resolve_download,
    upload_resolver=resolve_upload,
)

thread = threading.Thread(
    target=server.start,
    daemon=True,
)

thread.start()


client = TCPFileClient(
    host="127.0.0.1",
    port=5006,
)
```

Download:

```python
client.download(
    request={
        "operation": "download",
        "file_name": "example.txt",
    },
    destination="downloads/example.txt",
)
```

Upload:

```python
client.upload(
    request={
        "operation": "upload",
    },
    file_path="uploads/example.txt",
)
```

---

# Persistent Bidirectional JSON Streaming

The TCP package also supports persistent bidirectional JSON streaming.

Unlike request-response communication, streaming maintains an open TCP connection through which either endpoint can send messages independently.

The streaming components are:

- `TCPStreamClient`
- `TCPStreamServer`
- `TCPStreamConnection` (internal connection implementation)

The client and server reuse the same length-prefixed JSON protocol used by the existing TCP transport.

## Communication Model

```text
TCPStreamClient                    TCPStreamServer
       │                                  │
       │ establish persistent connection  │
       ├─────────────────────────────────►│
       │                                  │
       │ JSON message                     │
       ├─────────────────────────────────►│
       │                                  │
       │ JSON message                     │
       │◄─────────────────────────────────┤
       │                                  │
       │ JSON message                     │
       ├─────────────────────────────────►│
       │                                  │
       │ connection remains open          │
       │                                  │
```

There is no requirement for each outgoing message to receive an immediate response.

Messages are application-defined dictionaries.

## TCPStreamClient

`TCPStreamClient` manages one persistent connection to a streaming server.

Constructor:

```python
TCPStreamClient(
    port: int,
    on_message,
    host: str = DEFAULT_HOST,
    timeout: float = DEFAULT_CONNECT_TIMEOUT,
    on_disconnect=None,
)
```

The `on_message` callback receives one decoded JSON dictionary.

The optional `on_disconnect` callback is invoked when the connection closes.

Public interface:

```python
client.connect()
client.send(message)
client.close()

client.connected
```

`connect()` establishes the TCP connection and starts a background receive loop.

`send()` transmits one framed JSON dictionary over the existing connection.

`close()` closes the connection.

The connection timeout applies to the initial connection attempt. The persistent receive loop does not use that timeout during normal idle periods.

## TCPStreamServer

`TCPStreamServer` manages a listening socket and multiple persistent client connections.

Constructor:

```python
TCPStreamServer(
    port: int,
    on_message,
    host: str = DEFAULT_HOST,
    accept_timeout: float = DEFAULT_ACCEPT_TIMEOUT,
    on_connect=None,
    on_disconnect=None,
)
```

The message callback receives:

```python
on_message(client_id, message)
```

Each accepted connection receives a unique server-side `client_id`.

Public interface:

```python
server.start()
server.send(client_id, message)
server.broadcast(message)
server.stop()

server.running
server.client_ids
```

`start()` starts the background accept loop and returns after the listening socket has been initialized.

`send()` targets a particular connected client.

`broadcast()` sends a message to the currently registered connections.

`stop()` closes the listening socket and active connections, then waits for the server accept thread to terminate.

The optional callbacks are:

```python
on_connect(client_id, address)
on_disconnect(client_id)
```

## Basic Bidirectional Example

Server:

```python
from framework.communication.transport import TCPStreamServer


def on_message(client_id, message):
    print("Received:", client_id, message)

    server.send(
        client_id,
        {"type": "ack", "value": message},
    )


server = TCPStreamServer(
    host="127.0.0.1",
    port=5200,
    on_message=on_message,
)

server.start()
```

Client:

```python
from framework.communication.transport import TCPStreamClient


def on_message(message):
    print("Server message:", message)


client = TCPStreamClient(
    host="127.0.0.1",
    port=5200,
    on_message=on_message,
)

client.connect()

client.send({
    "type": "sample",
    "value": 10,
})
```

The server and client must run in processes or execution contexts that remain active while communication is required.

## Connection Lifecycle

Streaming connections have an explicit lifecycle:

```text
disconnected
     │
     │ connect()
     ▼
connected
     │
     ├── send messages
     │
     ├── receive messages
     │
     ▼
disconnected
     │
     │ connect()
     ▼
connected
```

A client can explicitly reconnect using the same `TCPStreamClient` instance after its previous connection has closed.

The server can also be stopped and restarted.

## Reconnection Policy

Automatic reconnection is not implemented by the transport.

This is intentional.

The transport provides connection operations and disconnection notifications, while the application decides:

- whether reconnection is appropriate;
- when to attempt reconnection;
- how long to wait between attempts;
- when to stop retrying;
- whether application state must be synchronized after reconnection.

This separation avoids coupling network recovery to application-specific execution or workflow state.

Applications should not perform blocking reconnection attempts directly inside receive callbacks.

## Message Delivery Semantics

Streaming uses TCP, which provides ordered byte delivery while a connection remains healthy.

However, successful completion of:

```python
client.send(message)
```

or:

```python
server.send(client_id, message)
```

does not prove that the remote application has received, interpreted, or processed the message.

It means the local socket send operation completed without reporting an error.

The streaming transport does not currently provide:

- application-level message acknowledgments;
- durable message queues;
- automatic message replay after reconnection;
- deduplication of repeated messages;
- exactly-once application processing guarantees.

Messages in transit when a connection fails may have an uncertain delivery outcome.

An application requiring confirmed processing must implement an acknowledgment protocol and any necessary persistence or deduplication.

Reconnection does not automatically resend previously transmitted messages.

## Error Handling

The internal `TCPStreamConnection` manages socket closure and reports unexpected receive-loop errors.

Normal remote disconnection is treated as a connection lifecycle event.

Exceptions raised by application message callbacks, including `ConnectionError`, are treated as application errors rather than silently interpreted as remote disconnection.

The connection is closed after a receive-loop error.

The transport remains independent of the meaning of application messages.

## Relationship to Other TCP Components

The TCP package now supports three communication patterns:

| Pattern | Components | Purpose |
|---|---|---|
| Request-response | `TCPClient`, `TCPServer` | One request and one response per connection |
| File transfer | `TCPFileClient`, `TCPFileServer` | Negotiated binary file upload and download |
| Bidirectional streaming | `TCPStreamClient`, `TCPStreamServer` | Persistent asynchronous JSON message exchange |

These components are independent and can be composed by higher-level applications as needed.


---

# Transport Boundaries

The TCP layer deliberately maintains the following separation:

```text
APPLICATION / WORKFLOW LAYER
│
│ commands
│ semantic requests
│ file resolution
│ application behavior
│
▼
────────────────────────────────────
TCP TRANSPORT
│
│ framed JSON messages
│ socket connections
│ request-response mechanics
│ file negotiation
│ raw byte streaming
│
▼
────────────────────────────────────
NETWORK
```

For ordinary messages:

```text
TCPServer
    │
    └── knows how to transport a dictionary

handler
    │
    └── knows what the dictionary means
```

For files:

```text
TCPFileServer
    │
    └── knows how to transfer a file

resolver
    │
    └── knows which file should be transferred
```

This allows the same TCP transport components to be reused by different applications without introducing application-specific behavior into the communication framework.

---

# Package API

The supported package-level imports are:

```python
from framework.communication.transport.tcp import (
    encode_message,
    receive_message,
    send_message,
    ok_response,
    error_response,
    TCPClient,
    TCPServer,
    get_file_info,
    send_file,
    receive_file,
    TCPFileClient,
    TCPFileServer,
)
```

These objects form the public API of `framework.communication.transport.tcp`.

Internal socket handling methods and implementation-specific helpers are not part of the public API.