# Communication Transport

The `framework.communication.transport` package provides the network transport layer used by the communication framework.

Its responsibility is to move structured messages and files between distributed processes while remaining independent of the meaning of those messages and files.

The current transport implementation is TCP.

The package-level public API is:

```python
from framework.communication.transport import (
    TCPClient,
    TCPServer,
    TCPFileClient,
    TCPFileServer,
    TCPStreamClient,
    TCPStreamServer,
)
```

## Responsibility

The transport layer provides:

- network communication between distributed processes;
- request-response communication;
- file transfer;
- client and server transport interfaces;
- separation between communication mechanics and application behavior.

It does **not**:

- define distributed actions or agents;
- persist action state;
- manage action lifecycle transitions;
- determine which agent should perform work;
- interpret application commands;
- execute operations;
- define orchestration logic;
- determine the semantic meaning or authoritative location of application files.

Those responsibilities belong to other framework or application layers.

---

# Package Structure

The current structure is:

```text
transport/
├── __init__.py
└── tcp/
    ├── __init__.py
    ├── config.py
    ├── protocol.py
    ├── tcp_client.py
    ├── tcp_server.py
    ├── stream_connection.py
    ├── stream_client.py
    ├── stream_server.py
    ├── file_transfer.py
    ├── file_client.py
    ├── file_server.py
    └── README.md
```

Conceptually:

```text
framework.communication.transport
              │
              ▼
             TCP
        ┌─────┴─────┐
        ▼           ▼
   JSON messages   files
```

The parent `transport` package exposes the main client and server classes, while protocol details and lower-level utilities remain available from the TCP subpackage.

---

# Transport Boundary

The transport layer sits between higher-level communication behavior and the network:

```text
HIGHER COMMUNICATION LAYERS
│
│ actions
│ commands
│ workflow requests
│ semantic file requests
│
▼
────────────────────────────────
TRANSPORT
│
│ connections
│ message transmission
│ request-response
│ file transfer
│
▼
────────────────────────────────
NETWORK
```

The transport layer is concerned with **how information moves**, not **what the information means**.

For example:

```python
client.send(
    {
        "command": "some_command",
        "value": 10,
    }
)
```

`TCPClient` knows how to send this dictionary and receive a response.

It does not know what `"some_command"` means.

Likewise, `TCPFileServer` knows how to transfer a resolved file but does not decide which application resource a request should represent.

---

# Message Transport

Structured communication is provided by:

```python
TCPClient
TCPServer
```

The basic interaction is:

```text
CLIENT                         SERVER

request dictionary
      │
      └──────────────────────► TCPServer
                                  │
                                  ▼
                              handler
                                  │
                                  ▼
response dictionary
      ◄───────────────────────────┘
```

`TCPClient` provides the client-side request-response interface.

`TCPServer` provides the server-side transport and delegates application behavior to a supplied handler.

Example:

```python
from framework.communication.transport import (
    TCPClient,
    TCPServer,
)
```

Detailed protocol framing, constructors, methods, error behavior, and examples are documented in the [TCP transport documentation](tcp/README.md).

---

# File Transport

File communication is provided by:

```python
TCPFileClient
TCPFileServer
```

The basic relationship is:

```text
CLIENT                         SERVER

semantic request
      │
      └──────────────────────► TCPFileServer
                                  │
                                  ▼
                               resolver
                                  │
                                  ▼
                              file path
                                  │
raw file bytes                   │
      ◄───────────────────────────┘
```

For uploads, the direction of the file bytes is reversed.

The important boundary is:

```text
application resolver
    │
    └── decides which file is involved

transport
    │
    └── moves the file bytes
```

This allows higher-level applications to use semantic identifiers without requiring clients to know server-local filesystem paths.

Example:

```python
from framework.communication.transport import (
    TCPFileClient,
    TCPFileServer,
)
```

Detailed download/upload protocols, resolver contracts, low-level file utilities, and examples are documented in the [TCP transport documentation](tcp/README.md).

---

# Current Transport Implementation

TCP is currently the only transport implementation provided by this package.

The parent package therefore exposes the main TCP interfaces directly:

```python
from framework.communication.transport import (
    TCPClient,
    TCPServer,
    TCPFileClient,
    TCPFileServer,
    TCPStreamClient,
    TCPStreamServer,
)
```

Code that only needs the high-level transport interfaces can import from:

```python
framework.communication.transport
```

Code that specifically needs TCP protocol utilities or low-level file-transfer functions can import from:

```python
framework.communication.transport.tcp
```

For example:

```python
from framework.communication.transport.tcp import (
    send_message,
    receive_message,
    send_file,
    receive_file,
)
```

---

# Public API

The public API exposed directly by `framework.communication.transport` is:

| Object | Purpose |
|---|---|
| `TCPClient` | Send one structured request and receive one structured response over TCP. |
| `TCPServer` | Receive structured TCP requests and delegate them to an application handler. |
| `TCPFileClient` | Download or upload files using negotiated TCP file transfer. |
| `TCPFileServer` | Serve negotiated file downloads and uploads using application-provided resolvers. |
| `TCPStreamClient` | Persistent bidirectional JSON client with explicit connection lifecycle. |
| `TCPStreamServer` | Multi-client bidirectional JSON server with targeted sends and broadcasts. |

The lower-level TCP package additionally exposes protocol and file-streaming utilities.

See:

[`framework/communication/transport/tcp/README.md`](tcp/README.md)

for the complete TCP API and protocol documentation.