# Communication Workflow

The `framework.communication.workflow` package provides reusable communication workflows for distributed agents.

It currently supports two independent communication models:

1. **Action workflow** — poll-based distributed action claiming, local execution-state persistence, and lifecycle synchronization.
2. **Streaming workflow** — persistent bidirectional communication between registered agents and a coordinating server.

Both models use the generic communication core and transport layers, but they serve different purposes and do not depend on each other.

The action workflow coordinates discrete units of work with durable execution state. The streaming workflow provides ongoing asynchronous message exchange between connected agents.

The public API is:

```python
from framework.communication.workflow import (
    Coordinator,
    WorkflowHandler,
    WorkflowClient,
    AgentWorkflowHandler,
    AgentPoller,
    StreamClient,
    StreamHandler,
)
```

## Responsibility

The workflow package provides:

### Action workflow

- Discovery and claiming of eligible pending actions.
- Authoritative workflow request handling.
- Agent-side action lifecycle communication.
- Persistence of claimed actions in an `AgentActionStore`.
- Polling for new work.
- Local action consumption.
- Synchronization of `RUNNING` and terminal states.

### Streaming workflow

- Agent registration over persistent TCP streaming connections.
- Registration acknowledgement and rejection.
- Association of active connections with `Agent` identities.
- Bidirectional asynchronous message exchange.
- Targeted server-to-agent communication.
- Connection and registration lifecycle management.

The workflow package does not:

- Execute application-specific operations.
- Define orchestration sequences.
- Implement socket mechanics or JSON framing.
- Define persistent workspace or entity structures.
- Automatically persist or replay streamed application messages.
- Provide authentication, encryption, or guaranteed message delivery.

Those responsibilities belong to other framework or application layers, or remain outside the currently implemented capabilities.


---


# Package Structure

```text
workflow/
├── __init__.py
│
├── coordinator.py
├── handler.py
├── client.py
├── agent_handler.py
├── agent_poller.py
│
├── stream_client.py
├── stream_handler.py
│
└── README.md
```

The package contains two independent groups of components.

### Action workflow

```text
AUTHORITATIVE SIDE

ActionStore
    │
    ▼
Coordinator
    │
    ▼
WorkflowHandler
    │
    │ request-response transport
    ▼
AGENT SIDE

WorkflowClient
    │
    ├── AgentActionStore
    ├── AgentPoller
    └── AgentWorkflowHandler
```

### Streaming workflow

```text
          COORDINATING SIDE

             StreamHandler
                   │
                   ▼
            TCPStreamServer
                   │
                   │ persistent TCP
                   │ bidirectional
                   │
            TCPStreamClient
                   ▲
                   │
              StreamClient

                AGENT SIDE
```

The streaming workflow can maintain multiple registered Agent connections through one `StreamHandler`.

The two workflow models may be composed by the same application, but neither requires the other.


---

# Distributed Workflow Model

The authoritative action lifecycle is:

```text
PENDING
   │
   │ claim
   ▼
CLAIMED
   │
   │ execution starts
   ▼
RUNNING
   │
   ├──────────────► COMPLETED
   ├──────────────► FAILED
   └──────────────► CANCELLED
```

The agent also maintains its own durable execution state:

```text
CLAIMED
   │
   │ executor consumes
   ▼
CONSUMED
   │
   │ RUNNING acknowledged
   ▼
RUNNING
   │
   │ executor finishes
   ▼
TERMINAL
   │
   │ terminal result acknowledged
   ▼
INACTIVE
```

`CONSUMED` is agent-local execution state and is not part of `ActionStatus`.

The workflow layer coordinates these two perspectives rather than merging them into one state representation.

---

# Coordinator

```python
class Coordinator
```

`Coordinator` performs authoritative distributed action coordination using an `ActionStore`.

Its current responsibility is intentionally small: find the next pending action that an agent can handle and claim it for that agent.

## Constructor

```python
Coordinator(
    action_store: ActionStore,
)
```

Example:

```python
from framework.communication.storage import (
    ActionStore,
)

from framework.communication.workflow import (
    Coordinator,
)

action_store = ActionStore(
    root="runtime/actions",
)

coordinator = Coordinator(
    action_store=action_store,
)
```

The supplied object must be an `ActionStore`.

---

## Public attributes

### `action_store`

```python
coordinator.action_store: ActionStore
```

The authoritative store used for action discovery and claiming.

---

## `claim_next()`

```python
coordinator.claim_next(
    agent: Agent,
) -> Action | None
```

Finds and claims the next pending action that the supplied agent can handle.

Example:

```python
from framework.communication.core import Agent

agent = Agent(
    agent_id="processing_pc_01",
    roles=["processing"],
)

action = coordinator.claim_next(
    agent
)
```

The method first asks the authoritative store for pending actions matching the agent's roles:

```text
Agent.roles
    │
    ▼
ActionStore.find_pending(
    targets=agent.roles
)
```

If no eligible action exists:

```python
None
```

is returned.

If one or more eligible actions exist, the first returned action is claimed:

```text
pending actions
      │
      ▼
pending[0]
      │
      ▼
ActionStore.claim()
      │
      ▼
CLAIMED Action
```

The `ActionStore` remains responsible for enforcing whether the claim itself is valid.

---

# WorkflowHandler

```python
class WorkflowHandler
```

`WorkflowHandler` exposes generic authoritative workflow operations through dictionary requests and responses.

It contains no project-specific behavior.

The handler currently supports:

```text
claim_next
mark_running
mark_terminal
```

## Constructor

```python
WorkflowHandler(
    action_store: ActionStore,
)
```

Example:

```python
from framework.communication.storage import (
    ActionStore,
)

from framework.communication.workflow import (
    WorkflowHandler,
)

action_store = ActionStore(
    root="runtime/actions",
)

handler = WorkflowHandler(
    action_store=action_store,
)
```

The constructor also creates a `Coordinator` using the same `ActionStore`.

---

## Public attributes

```python
handler.action_store
handler.coordinator
```

`action_store` is the authoritative action store.

`coordinator` handles eligible action discovery and claiming.

---

## `handle()`

```python
handler.handle(
    request: dict,
) -> dict
```

Processes one workflow request.

The request must be a dictionary.

The `command` value is stripped and normalized to lowercase before routing.

If no command is provided:

```python
{
    "status": "error",
    "message": "Missing command.",
}
```

is returned.

Unknown commands similarly return an error response.

---

# `claim_next` Command

Request:

```python
{
    "command": "claim_next",
    "agent": {
        "agent_id": "processing_pc_01",
        "roles": ["processing"],
        "metadata": {},
    },
}
```

The handler reconstructs the `Agent` and passes it to:

```python
Coordinator.claim_next()
```

When an eligible action exists, the response is:

```python
{
    "status": "ok",
    "action": {
        ...
    },
}
```

The returned action is already authoritatively `CLAIMED`.

When no eligible action exists:

```python
{
    "status": "ok",
    "action": None,
}
```

is returned.

Errors encountered during processing are returned as:

```python
{
    "status": "error",
    "message": "...",
}
```

---

# `mark_running` Command

Request:

```python
{
    "command": "mark_running",
    "action_id": "action-001",
    "agent": {
        ...
    },
}
```

The handler delegates the transition to:

```python
ActionStore.mark_running()
```

The authoritative transition is:

```text
CLAIMED
   ↓
RUNNING
```

On success:

```python
{
    "status": "ok",
    "action": {
        ...
    },
}
```

is returned.

The `ActionStore` enforces ownership and lifecycle validity.

---

# `mark_terminal` Command

Request:

```python
{
    "command": "mark_terminal",
    "action_id": "action-001",
    "action_status": "completed",
    "agent": {
        ...
    },
}
```

`action_status` is converted to `ActionStatus` before being passed to:

```python
ActionStore.mark_terminal()
```

Valid terminal states are:

```text
completed
failed
cancelled
```

The normal authoritative transition is:

```text
RUNNING
   ↓
COMPLETED / FAILED / CANCELLED
```

On success, the serialized authoritative action is returned.

---

# WorkflowClient

```python
class WorkflowClient
```

`WorkflowClient` is the agent-side interface to a remote workflow handler.

It combines:

```text
TCPClient
    +
Agent
    +
AgentActionStore
```

to provide agent-side workflow operations.

## Constructor

```python
WorkflowClient(
    tcp_client: TCPClient,
    agent: Agent,
    local_store: AgentActionStore,
)
```

Example:

```python
from framework.communication.core import Agent
from framework.communication.storage import (
    AgentActionStore,
)
from framework.communication.transport import (
    TCPClient,
)
from framework.communication.workflow import (
    WorkflowClient,
)

agent = Agent(
    agent_id="processing_pc_01",
    roles=["processing"],
)

local_store = AgentActionStore(
    root="runtime/processing_pc_01",
    agent=agent,
)

tcp_client = TCPClient(
    host="127.0.0.1",
    port=5005,
)

workflow_client = WorkflowClient(
    tcp_client=tcp_client,
    agent=agent,
    local_store=local_store,
)
```

The `AgentActionStore` must belong to the same `agent_id` as the supplied `Agent`.

---

## Public attributes

```python
workflow_client.tcp_client
workflow_client.agent
workflow_client.local_store
```

These represent the remote transport client, agent identity, and durable local action store used by the workflow client.

---

## `claim_next()`

```python
workflow_client.claim_next() -> Action | None
```

Requests the next eligible action from the authoritative workflow handler.

The request is:

```python
{
    "command": "claim_next",
    "agent": workflow_client.agent.to_dict(),
}
```

If no action is available:

```python
None
```

is returned.

If an action is returned, the client:

```text
receives action dictionary
        │
        ▼
Action.from_dict()
        │
        ▼
AgentActionStore.save()
        │
        ▼
returns Action
```

Therefore a successfully claimed remote action is persisted locally before `claim_next()` returns it.

If the remote response reports an error, `RuntimeError` is raised.

---

## `mark_running()`

```python
workflow_client.mark_running(
    action_id: str,
) -> Action
```

Reports that a claimed action has started running.

The client sends:

```python
{
    "command": "mark_running",
    "action_id": "...",
    "agent": workflow_client.agent.to_dict(),
}
```

On success, the authoritative `RUNNING` action is reconstructed and returned.

This method reports remote state only.

It does not update `AgentActionStore.local_status`; that local acknowledgement is handled separately by the agent-local workflow logic.

---

## `mark_terminal()`

```python
workflow_client.mark_terminal(
    action_id: str,
    status: str,
) -> Action
```

Reports a terminal result to the authoritative workflow handler.

Accepted status values are:

```text
completed
failed
cancelled
```

Example:

```python
terminal_action = (
    workflow_client.mark_terminal(
        action_id="action-001",
        status="completed",
    )
)
```

On success, the authoritative terminal `Action` is returned.

An invalid terminal status is rejected before the request is sent.

---

# AgentWorkflowHandler

```python
class AgentWorkflowHandler
```

`AgentWorkflowHandler` provides the workflow interface used by software running locally on an agent.

It coordinates:

```text
local executor
      │
      ▼
AgentWorkflowHandler
      │
      ├── AgentActionStore
      │
      └── WorkflowClient
                │
                ▼
        authoritative workflow
```

The handler contains no transport-specific or project-specific execution logic.

Its current commands are:

```text
consume_action
mark_terminal
```

## Constructor

```python
AgentWorkflowHandler(
    local_store: AgentActionStore,
    workflow_client: WorkflowClient,
)
```

The local store and workflow client must belong to the same agent.

---

## Public attributes

```python
handler.local_store
handler.workflow_client
```

---

## `handle()`

```python
handler.handle(
    request: dict,
) -> dict
```

Routes an agent-local workflow request.

Example:

```python
response = handler.handle(
    {
        "command": "consume_action",
    }
)
```

Missing or unknown commands produce an error response.

---

# `consume_action` Command

`consume_action` exposes a locally claimed action to the local executor and synchronizes the start of execution with the authoritative side.

Request:

```python
{
    "command": "consume_action",
}
```

If no unconsumed local action exists:

```python
{
    "status": "ok",
    "trigger": False,
    "action": None,
}
```

is returned.

If an action is available, the sequence is:

```text
AgentActionStore.find_unconsumed()
        │
        ▼
local action found
        │
        ▼
mark_consumed()
        │
        ▼
local_status = consumed
        │
        ▼
WorkflowClient.mark_running()
        │
        ▼
authoritative status = RUNNING
        │
        ▼
mark_running_reported()
        │
        ▼
local_status = running
        │
        ▼
return trigger=True
```

The successful response contains the authoritative running action:

```python
{
    "status": "ok",
    "trigger": True,
    "action": {
        ...
    },
}
```

A key ordering rule is:

> The action is consumed locally before `RUNNING` is reported remotely.

This preserves the fact that the local executor took ownership of the work before the authoritative execution state advances.

---

# `mark_terminal` Agent Command

After execution finishes, the local executor reports its outcome through:

```python
{
    "command": "mark_terminal",
    "action_status": "completed",
}
```

Valid outcomes are:

```text
completed
failed
cancelled
```

The sequence is:

```text
find active local action
        │
        ▼
AgentActionStore.mark_terminal()
        │
        ▼
terminal outcome durable locally
terminal_reported = False
        │
        ▼
WorkflowClient.mark_terminal()
        │
        ▼
authoritative terminal state
        │
        ▼
AgentActionStore.mark_terminal_reported()
        │
        ▼
terminal_reported = True
        │
        ▼
local action becomes inactive
```

This ordering follows the execution-ownership principle:

> The executing side records its own outcome locally before reporting that outcome to the authoritative side.

The local action remains active until the terminal result has been acknowledged.

---

# AgentPoller

```python
class AgentPoller
```

`AgentPoller` continuously looks for distributed work on behalf of an agent.

Its most important rule is:

> Never claim another action while the agent still has an active local action.

The polling sequence is:

```text
check AgentActionStore.find_active()
        │
        ├── active action exists
        │       │
        │       └── return existing action
        │
        └── no active action
                │
                ▼
        WorkflowClient.claim_next()
                │
                ├── no action → None
                │
                └── action claimed
                        │
                        ▼
                  persisted locally
```

## Constructor

```python
AgentPoller(
    workflow_client: WorkflowClient,
    local_store: AgentActionStore,
    interval: float = 1.0,
)
```

Example:

```python
from framework.communication.workflow import (
    AgentPoller,
)

poller = AgentPoller(
    workflow_client=workflow_client,
    local_store=local_store,
    interval=1.0,
)
```

The workflow client and local store must belong to the same agent.

`interval` must be greater than zero.

---

## Public attributes

```python
poller.workflow_client
poller.local_store
poller.interval
```

Threading state such as `_thread`, `_stop_event`, and `_lock` is internal implementation state and is not part of the public API.

---

## `poll_once()`

```python
poller.poll_once() -> dict | None
```

Performs one polling cycle.

It can return:

1. the existing active local action;
2. a newly claimed and locally persisted action;
3. `None` when no action is available.

The local store is always checked first:

```text
find_active()
    │
    ├── found → return it
    │
    └── none  → ask authoritative side
```

This is what prevents an agent from claiming additional work while its current action is:

- claimed;
- consumed;
- running;
- terminal but not yet acknowledged.

Only after the previous local action is terminal and `terminal_reported=True` can polling claim another action.

---

## `start()`

```python
poller.start() -> bool
```

Starts the background polling thread.

The thread is created as a daemon thread.

Returns:

```text
True     a new polling thread was started
False    a polling thread is already running
```

The background loop repeatedly calls:

```python
poller.poll_once()
```

and waits for `interval` seconds between cycles.

Polling exceptions are printed but do not terminate the background loop.

---

## `stop()`

```python
poller.stop(
    join_timeout: float = 2.0,
) -> bool
```

Requests the background polling thread to stop.

Returns:

```text
True     an active polling thread was asked to stop
False    no active polling thread existed
```

The method signals the internal stop event and waits up to `join_timeout` seconds for the thread.

---

# Complete Distributed Flow

The workflow components work together as follows:

```text
AUTHORITATIVE SIDE                         AGENT SIDE

ActionStore
    │
    │ PENDING
    ▼
WorkflowHandler
    ▲
    │                                  AgentPoller
    │                                      │
    │        claim_next                    │
    │◄─────────────────────────────────────┤
    │                                      │
Coordinator                                │
    │                                      │
    ▼                                      │
ActionStore.claim()                        │
    │                                      │
    │ CLAIMED Action                       │
    ├─────────────────────────────────────►│
    │                                      ▼
    │                              AgentActionStore
    │                                      │
    │                              local CLAIMED
    │                                      │
    │                              local executor
    │                                      │
    │                              consume_action
    │                                      │
    │                              local CONSUMED
    │                                      │
    │        mark_running                  │
    │◄─────────────────────────────────────┤
    │                                      │
ActionStore.mark_running()                 │
    │                                      │
    │ RUNNING acknowledgement              │
    ├─────────────────────────────────────►│
    │                                      │
    │                              local RUNNING
    │                                      │
    │                              operation executes
    │                                      │
    │                              local TERMINAL
    │                                      │
    │        mark_terminal                 │
    │◄─────────────────────────────────────┤
    │                                      │
ActionStore.mark_terminal()                │
    │                                      │
    │ terminal acknowledgement             │
    ├─────────────────────────────────────►│
                                           │
                                   terminal_reported=True
                                           │
                                           ▼
                                      INACTIVE
```

---

# Separation of Responsibilities

The workflow package deliberately separates several responsibilities.

## Coordinator

```text
Which pending action can this agent claim?
```

## WorkflowHandler

```text
How are authoritative workflow commands exposed?
```

## WorkflowClient

```text
How does an agent request and report workflow state remotely?
```

## AgentActionStore

```text
What execution state must this agent remember durably?
```

## AgentWorkflowHandler

```text
How does a local executor consume work and report its outcome?
```

## AgentPoller

```text
When is this agent free to ask for another action?
```

Keeping these responsibilities separate prevents transport, persistence, execution, and application logic from becoming one monolithic agent service.

---

# Workflow Boundary

The workflow layer coordinates distributed execution state, but it does not perform the application operation itself.

The intended boundary is:

```text
distributed coordination
        │
        ▼
AgentWorkflowHandler
        │
        │ returns executable Action
        ▼
APPLICATION EXECUTOR
        │
        │ performs operation
        ▼
AgentWorkflowHandler
        │
        │ terminal result
        ▼
distributed coordination
```

This allows the executor to change independently of the communication protocol.

A local executor may be:

- a Python application;
- another local service;
- a visual programming environment;
- a robotic control process;
- another application capable of communicating with the agent.

The workflow framework only coordinates the action lifecycle around that execution.

---

# Important State Ownership Rule

The workflow architecture follows this principle:

> **Status ownership follows execution ownership.**

The authoritative store owns distributed action state.

The executing agent owns its local execution outcome first.

Therefore terminal synchronization follows:

```text
executor finishes
      ↓
persist terminal outcome locally
      ↓
report terminal outcome
      ↓
authoritative side accepts
      ↓
persist acknowledgement locally
```

This is why a terminal local action remains active until:

```python
terminal_reported == True
```

The agent should not accept new work before that synchronization completes.


---

# Streaming Workflow

The streaming workflow provides persistent bidirectional communication between distributed agents and a coordinating server.

It is implemented by:

- `StreamClient` — agent-side connection, registration, and message interface.
- `StreamHandler` — coordinating-side registration management and Agent-aware message dispatch.

The workflow uses:

- `Agent` from `framework.communication.core`;
- `TCPStreamClient` and `TCPStreamServer` from `framework.communication.transport`.

Unlike the action workflow, the streaming workflow does not claim Actions, modify `ActionStatus`, or interact with `ActionStore` or `AgentActionStore`.

## Communication Model

```text
                 STREAM HANDLER
                  coordinating
                      side
                       │
              ┌────────┼────────┐
              │        │        │
              ▼        ▼        ▼
           Agent A  Agent B  Agent C
              │        │        │
              └────────┼────────┘
                       │
             persistent bidirectional
                 TCP connections
```

Each registered Agent has its own transport connection.

The coordinating side can send a message to a specific Agent by its `agent_id`.

Agents can send application messages to the coordinating side through their persistent connections.

Messages are dictionaries encoded as framed JSON by the underlying TCP transport.

---

# StreamClient

```python
class StreamClient
```

`StreamClient` provides the agent-side streaming workflow interface.

It combines a transport-independent `Agent` identity with a persistent `TCPStreamClient`.

## Constructor

```python
StreamClient(
    agent: Agent,
    host: str,
    port: int,
    on_message: Callable[[dict], None],
    on_disconnect: Callable[[], None] | None = None,
    registration_timeout: float = 5.0,
)
```

Parameters:

| Parameter | Purpose |
|---|---|
| `agent` | Agent identity and capabilities to register. |
| `host` | Coordinating server address. |
| `port` | Streaming server port. |
| `on_message` | Callback for incoming application messages. |
| `on_disconnect` | Optional callback invoked on disconnection. |
| `registration_timeout` | Maximum time to wait for registration acknowledgement, in seconds. |

`agent` must be an `Agent`, `on_message` must be callable, and `registration_timeout` must be positive.

## Public Attributes and Properties

```python
stream_client.agent
stream_client.on_message
stream_client.on_disconnect
stream_client.registration_timeout
stream_client.tcp_client

stream_client.connected
stream_client.registered
```

`connected` indicates the underlying TCP connection state.

`registered` indicates that the Agent has received a successful registration acknowledgement and remains connected.

These states are distinct:

```text
TCP connected
     │
     ▼
registration requested
     │
     ▼
registration acknowledged
     │
     ▼
Agent registered
```

A connected transport is not necessarily a registered Agent.

## `connect()`

```python
stream_client.connect()
```

Establishes the TCP connection, sends the Agent registration request, and waits for acknowledgement.

The registration request is:

```python
{
    "type": "agent_register",
    "agent": agent.to_dict(),
}
```

The method returns successfully only after receiving an accepted registration response.

A rejected registration raises `ConnectionError`.

A missing acknowledgement within `registration_timeout` raises `TimeoutError`.

On registration failure, the client closes the underlying connection.

## `send()`

```python
stream_client.send(message: dict)
```

Sends an application message through the registered connection.

Example:

```python
stream_client.send({
    "type": "sensor_data",
    "value": 42,
})
```

The client must be registered before sending application messages.

The following message types are reserved for the registration protocol:

```text
agent_register
agent_registered
agent_rejected
```

Applications must not send these through `StreamClient.send()`.

## `close()`

```python
stream_client.close()
```

Closes the underlying TCP connection and clears the client's registered state.

## Reconnection

Reconnection is explicit.

After disconnection or registration rejection, the application may call `connect()` again.

Automatic reconnection, application message replay, and restoration of previous application state are not provided.

---

# StreamHandler

```python
class StreamHandler
```

`StreamHandler` provides coordinating-side registration management and Agent-aware message dispatch.

It wraps a generic `TCPStreamServer` and maintains mappings between registered Agent IDs and active transport connections.

## Constructor

```python
StreamHandler(
    host: str,
    port: int,
    on_message: Callable[[Agent, dict], None],
)
```

The callback receives:

```python
on_message(agent, message)
```

where `agent` is the registered `Agent` associated with the connection.

## Public Attributes and Properties

```python
stream_handler.on_message
stream_handler.tcp_server
stream_handler.connected_agents
```

`connected_agents` returns the IDs of currently registered Agents.

## `start()`

```python
stream_handler.start()
```

Starts the underlying TCP streaming server.

The server supports multiple concurrent transport connections.

## `stop()`

```python
stream_handler.stop()
```

Stops the streaming server and closes its active connections.

Disconnection callbacks remove the associated Agent registrations.

## `send()`

```python
stream_handler.send(
    agent_id: str,
    message: dict,
)
```

Sends an application message to the registered Agent identified by `agent_id`.

Example:

```python
stream_handler.send(
    "sensing_pc_01",
    {
        "type": "control",
        "value": "start",
    },
)
```

If the Agent is not registered, `ConnectionError` is raised.

The handler does not expose a workflow-level broadcast method. Applications needing broadcast behavior can iterate over `connected_agents` and call `send()` for each registered Agent.

---

# Registration Protocol

Agent registration is required before the coordinating side dispatches application messages.

## Successful Registration

```text
StreamClient                     StreamHandler
     │                                │
     │       TCP connection           │
     ├───────────────────────────────►│
     │                                │
     │       agent_register           │
     ├───────────────────────────────►│
     │                                │
     │                          validate Agent
     │                          check duplicate ID
     │                          store registration
     │                                │
     │       agent_registered         │
     │◄───────────────────────────────┤
     │                                │
     ▼                                ▼
registered                       registered
```

Request:

```python
{
    "type": "agent_register",
    "agent": {
        "agent_id": "sensing_pc_01",
        "roles": ["sensing"],
        "metadata": {},
    },
}
```

Acknowledgement:

```python
{
    "type": "agent_registered",
    "agent_id": "sensing_pc_01",
}
```

The acknowledgement identifies the accepted Agent.

`StreamClient.connect()` waits for this response before completing.

## Registration Rejection

The server rejects invalid registrations and duplicate Agent IDs.

A rejection response has the structure:

```python
{
    "type": "agent_rejected",
    "reason": "...",
}
```

For example:

```python
{
    "type": "agent_rejected",
    "reason": "Agent already connected: sensing_pc_01",
}
```

The client converts registration rejection into `ConnectionError` and closes its connection.

The coordinating side also rejects application messages received from connections that have not registered an Agent.

The current handler sends a rejection response but does not forcibly disconnect every rejected raw transport client.

## Duplicate Agent IDs

Only one active registration is allowed for a given Agent ID.

When two connections attempt to register the same Agent ID concurrently, only one registration can succeed.

The registration mappings are protected by a lock.

A rejected duplicate does not replace or disconnect the existing registered Agent.

## Connection Cleanup

When a registered connection disconnects, the handler removes its Agent registration and connection mappings.

This makes the Agent ID available for a later registration.

---

# Streaming Workflow Example

The following example demonstrates communication between one coordinating server and one Agent.

## Coordinating Side

```python
from framework.communication.workflow import (
    StreamHandler,
)


def on_agent_message(agent, message):
    print(
        f"Received from {agent.agent_id}:",
        message,
    )


handler = StreamHandler(
    host="127.0.0.1",
    port=6005,
    on_message=on_agent_message,
)

handler.start()
```

The server starts its background accept loop and can then receive Agent registrations.

## Agent Side

```python
from framework.communication.core import Agent
from framework.communication.workflow import StreamClient


def on_master_message(message):
    print("Received from coordinator:", message)


agent = Agent(
    agent_id="sensing_pc_01",
    roles=["sensing"],
)

client = StreamClient(
    agent=agent,
    host="127.0.0.1",
    port=6005,
    on_message=on_master_message,
)

client.connect()

client.send({
    "type": "sensor_data",
    "value": 42,
})
```

After successful registration, the coordinating side can send a targeted message:

```python
handler.send(
    "sensing_pc_01",
    {
        "type": "control",
        "value": "start",
    },
)
```

The Agent receives this message through its `on_message` callback.

The applications should close their respective connections and server during shutdown:

```python
client.close()
handler.stop()
```

The examples assume the coordinating and Agent code run in separate execution contexts or that the server is already running.

---

# Streaming Lifecycle

The Agent-side lifecycle is:

```text
DISCONNECTED
     │
     │ connect()
     ▼
TCP CONNECTED
     │
     │ agent_register
     ▼
REGISTERING
     │
     ├── accepted ──► REGISTERED
     │                    │
     │                    ├── send messages
     │                    ├── receive messages
     │                    └── disconnect
     │                             │
     │                             ▼
     │                       DISCONNECTED
     │
     ├── rejected ──► DISCONNECTED
     │
     └── timeout ───► DISCONNECTED
```

These are conceptual connection and registration states, not members of `ActionStatus`.

The streaming workflow does not maintain an authoritative persistent state machine for application messages.

---

# Relationship to the Action Workflow

The action workflow and streaming workflow are independent.

| Aspect | Action Workflow | Streaming Workflow |
|---|---|---|
| Main purpose | Distributed execution lifecycle | Ongoing message exchange |
| Communication | Request-response and polling | Persistent bidirectional TCP |
| Agent identity | `Agent` | `Agent` |
| Authoritative ActionStore | Required | Not required |
| AgentActionStore | Used for local durability | Not required |
| ActionStatus transitions | Managed | Not managed |
| Registration handshake | Not used | Required |
| Application execution | External | External |
| Automatic message persistence | Action-state persistence | Not provided |

An application may use both workflows simultaneously.

For example, discrete operations may be coordinated through Actions while continuous sensor updates are exchanged through streaming.

However, streaming messages do not automatically create, claim, or complete Actions.

---

# Streaming Delivery and Security Boundaries

The registration protocol establishes an association between a TCP connection and an Agent identity supplied by the connecting client.

It is not an authentication mechanism.

The current streaming workflow does not provide:

- Authentication or authorization.
- TLS encryption.
- Automatic reconnection.
- Application-level delivery acknowledgements.
- Durable streaming message storage.
- Automatic message replay.
- Deduplication or exactly-once processing.
- Automatic recovery of application state.

A successful transport send does not prove that the receiving application has processed a message.

Applications requiring stronger guarantees must implement the appropriate higher-level mechanisms.

Callbacks run on transport receive threads, so application callbacks should avoid long-running blocking operations.

---

# Streaming Tests

The streaming workflow is tested separately from the poll-based Action workflow.

## Integration Tests

```bash
python -m framework.test_files.test_stream_workflow
```

The integration suite covers:

- Multiple Agent registrations.
- Agent-to-coordinator messages.
- Targeted coordinator-to-Agent messages.
- Independent disconnections.
- Continued communication by remaining Agents.
- Agent reconnection.
- Duplicate registration rejection.
- Unregistered message rejection.
- Controlled shutdown.

## Robustness Tests

```bash
python -m framework.test_files.test_stream_workflow_robustness
```

The robustness suite covers:

- Invalid registration payloads.
- Concurrent duplicate registration attempts.
- Registration acknowledgement timeout.
- Reconnection after rejection.
- Master shutdown, registration cleanup, and restart.

These tests have been executed successfully in the current development environment.

The generic TCP streaming transport also has independent tests covering connection lifecycle, concurrency, reconnection, and shutdown behavior.

The tests establish the behavior of the scenarios exercised; they do not establish guaranteed delivery or reliability across every possible network failure.


---


# Package API

The supported package-level imports are:

```python
from framework.communication.workflow import (
    Coordinator,
    WorkflowHandler,
    WorkflowClient,
    AgentWorkflowHandler,
    AgentPoller,
    StreamClient,
    StreamHandler,
)
```

| Object | Purpose |
|---|---|
| `Coordinator` | Find and claim the next eligible authoritative Action. |
| `WorkflowHandler` | Handle authoritative Action workflow commands. |
| `WorkflowClient` | Agent-side claiming and lifecycle reporting. |
| `AgentWorkflowHandler` | Coordinate local Action consumption and terminal reporting. |
| `AgentPoller` | Poll for work when no active local Action exists. |
| `StreamClient` | Agent-side persistent streaming, registration, and messaging. |
| `StreamHandler` | Coordinating-side Agent registration and targeted message dispatch. |

The package intentionally separates poll-based Action coordination from persistent streaming communication.

Transport-level details are documented in:

- [Transport README](../transport/README.md)
- [TCP Transport README](../transport/tcp/README.md)