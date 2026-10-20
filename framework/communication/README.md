# Communication Framework

The `framework.communication` package provides reusable infrastructure for coordinating distributed work between independent software processes.

It defines how work is represented, how agents identify the work they can perform, how actions are persisted and claimed, how execution state is synchronized, and how messages and files move between distributed processes.

The communication framework is organized into four layers:

```text
communication/
├── core/
├── storage/
├── transport/
└── workflow/
```

Together they provide the distributed execution model:

```text
action created
     │
     ▼
authoritative action store
     │
     ▼
eligible agent claims action
     │
     ▼
action persisted on agent
     │
     ▼
local executor consumes action
     │
     ▼
execution state synchronized
     │
     ▼
operation executes
     │
     ▼
terminal result persisted locally
     │
     ▼
terminal result synchronized
     │
     ▼
agent becomes available again
```

## Purpose

The communication framework is intended for systems where different operations may execute in different processes or on different computers.

For example:

```text
COMPUTER A                         COMPUTER B

authoritative process             agent process
       │                               │
       │                               │
       │       distributed action      │
       ├──────────────────────────────►│
       │                               │
       │                               ▼
       │                         local executor
       │                               │
       │                         performs work
       │                               │
       │       execution status        │
       │◄──────────────────────────────┤
       │                               │
```

The executor itself is deliberately outside the communication framework.

It may be:

- a Python application;
- a robotic control process;
- a visual programming environment;
- another local service;
- another application capable of communicating with the agent.

The communication framework coordinates the work around that executor without defining how the operation itself is performed.

---

# Main Concepts

A distributed workflow is built around three fundamental concepts:

```text
Action
Agent
Execution State
```

The communication framework supports both discrete Action coordination and persistent Agent-aware streaming. The Action lifecycle described below applies specifically to the poll-based Action workflow. Streaming communication is independent of that lifecycle and does not require Action persistence.

## Action

An `Action` represents a unit of distributed work.

For example:

```python
from framework.communication.core import Action

action = Action(
    action="process_data",
    target="processing",
    payload={
        "source": "dataset_01",
    },
)
```

The action says:

```text
WHAT should happen
    │
    └── action

WHO can perform it
    │
    └── target

WHAT information is needed
    │
    └── payload
```

Actions also carry lifecycle state, identity, claimant information, and metadata.

---

## Agent

An `Agent` represents the identity and capabilities of one distributed participant.

```python
from framework.communication.core import Agent

agent = Agent(
    agent_id="processing_pc_01",
    roles=[
        "processing",
    ],
)
```

The relationship between actions and agents is capability-based:

```text
Action.target
      │
      ▼
Agent.roles
```

An agent can claim an action when it has a role matching the action's target.

This separates:

```text
action definition
       from
physical execution location
```

The same type of action can therefore be executed by any eligible agent.

---

# Action Lifecycle

The authoritative distributed lifecycle is:

```text
PENDING
   │
   │ eligible agent claims action
   ▼
CLAIMED
   │
   │ executor begins execution
   ▼
RUNNING
   │
   ├──────────────► COMPLETED
   ├──────────────► FAILED
   └──────────────► CANCELLED
```

These states are defined by `ActionStatus`.

```python
from framework.communication.core import (
    ActionStatus,
)
```

The authoritative state represents the shared distributed view of the action.

However, distributed execution requires another perspective as well: the local state of the executing agent.

---

# Two-Sided State Model

A central design principle of the communication framework is that authoritative distributed state and agent-local execution state are stored separately.

```text
AUTHORITATIVE SIDE                  AGENT SIDE

ActionStore                         AgentActionStore

Action.status                       local_status
                                    consumed
                                    terminal_reported
```

The authoritative side answers:

```text
What is the distributed state
of this action?
```

The agent-local side answers:

```text
What has actually happened
to this action on this agent?
```

These are related, but they are not identical.

---

# Why Agent-Local State Exists

Consider an action that has been claimed by an agent.

The authoritative side may contain:

```text
CLAIMED
```

The agent then needs to remember whether:

- the action has been persisted locally;
- a local executor has consumed it;
- execution has started;
- execution has finished;
- the final result has been acknowledged remotely.

This produces the local execution lifecycle:

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
COMPLETED / FAILED / CANCELLED
   │
   │ terminal result acknowledged
   ▼
INACTIVE
```

`CONSUMED` is a local execution state.

It is not an `ActionStatus`.

---

# Status Ownership

The communication architecture follows an important rule:

> **Status ownership follows execution ownership.**

The authoritative side owns the shared distributed action state.

The executing agent owns the immediate result of its own execution.

Therefore an execution result is recorded locally first:

```text
executor finishes
      │
      ▼
agent persists terminal result
      │
      ▼
agent reports result
      │
      ▼
authoritative side accepts result
      │
      ▼
agent records acknowledgement
```

This ordering allows the executing side to retain its result even when communication is interrupted.

---

# Complete Distributed Lifecycle

A normal action passes through the following sequence.

## 1. Action exists authoritatively

```text
ActionStore

PENDING
```

The action is available for an eligible agent.

---

## 2. Agent polls for work

```text
AgentPoller
     │
     ▼
check local active action
```

Before requesting new work, the agent checks its own durable local state.

If an active action already exists:

```text
do not claim another action
```

If the agent is free:

```text
request next eligible action
```

---

## 3. Action is claimed

The agent sends its identity and roles to the authoritative workflow service.

```text
Agent
  │
  │ claim_next
  ▼
WorkflowHandler
  │
  ▼
Coordinator
  │
  ▼
ActionStore
```

The coordinator finds pending actions whose targets match the agent's roles.

The selected action transitions:

```text
PENDING
   ↓
CLAIMED
```

and records the claiming agent.

---

## 4. Claimed action is persisted locally

The agent receives the claimed action through `WorkflowClient`.

Before returning it as successfully claimed, the client stores it in:

```text
AgentActionStore
```

The agent therefore has durable local knowledge of the work it owns.

Initial local state:

```text
local_status      = claimed
consumed          = False
terminal_reported = False
```

---

## 5. Local executor consumes the action

Software running locally on the agent requests:

```text
consume_action
```

through `AgentWorkflowHandler`.

The action is first marked locally as consumed:

```text
CLAIMED
   ↓
CONSUMED
```

Only then is `RUNNING` reported to the authoritative side.

---

## 6. Running state is synchronized

The agent reports:

```text
mark_running
```

through `WorkflowClient`.

The authoritative action transitions:

```text
CLAIMED
   ↓
RUNNING
```

After successful acknowledgement, the agent records:

```text
local_status = running
```

The executor can now continue performing the actual operation.

---

## 7. Executor finishes

The operation itself occurs outside the communication framework.

The executor eventually determines one of three outcomes:

```text
completed
failed
cancelled
```

It reports that outcome through the agent-local workflow interface.

---

## 8. Terminal result is persisted locally

Before contacting the authoritative side, the agent records:

```text
local_status = completed
```

or:

```text
local_status = failed
```

or:

```text
local_status = cancelled
```

and:

```text
terminal_reported = False
```

The result is therefore durable on the executing side before synchronization begins.

---

## 9. Terminal result is synchronized

The agent reports the terminal result to the authoritative workflow service.

The authoritative action transitions:

```text
RUNNING
   ↓
COMPLETED / FAILED / CANCELLED
```

After acknowledgement, the agent records:

```text
terminal_reported = True
```

---

## 10. Agent becomes available

A terminal local action remains active until:

```python
terminal_reported == True
```

Only then does the poller consider the agent free to claim another action.

Therefore:

```text
operation finished
      ≠
agent immediately available
```

Instead:

```text
operation finished
      │
      ▼
terminal result synchronized
      │
      ▼
agent available
```

---

# Architecture Overview

The main communication components fit together as follows:

```text
                    AUTHORITATIVE SIDE

                         ActionStore
                              ▲
                              │
                         Coordinator
                              ▲
                              │
                       WorkflowHandler
                              ▲
                              │
                              │ TCP
                              │
                              ▼
                       WorkflowClient
                              │
             ┌────────────────┴────────────────┐
             │                                 │
             ▼                                 ▼
      AgentActionStore                   AgentPoller
             ▲
             │
      AgentWorkflowHandler
             ▲
             │
             ▼
        LOCAL EXECUTOR


                         AGENT SIDE
```

Each component has a deliberately narrow responsibility.

---

# Core Layer

Directory:

```text
framework/communication/core/
```

The core layer defines the transport-independent data models:

```python
from framework.communication.core import (
    Action,
    ActionStatus,
    Agent,
)
```

It answers:

```text
What is an action?
What states can an action have?
What is an agent?
Can this agent handle this target?
```

It does not persist, communicate, claim, poll, or execute anything.

Detailed documentation:

[`core/README.md`](core/README.md)

---

# Storage Layer

Directory:

```text
framework/communication/storage/
```

The storage layer provides:

```python
from framework.communication.storage import (
    ActionStore,
    AgentActionStore,
)
```

`ActionStore` owns authoritative distributed action persistence.

`AgentActionStore` owns durable local execution state for one agent.

Conceptually:

```text
ActionStore
    │
    └── shared authoritative lifecycle

AgentActionStore
    │
    └── agent-local execution lifecycle
```

The storage layer also enforces lifecycle and ownership rules associated with those persisted states.

Detailed documentation:

[`storage/README.md`](storage/README.md)

---


# Transport Layer

Directory:

```text
framework/communication/transport/
```

The transport layer moves information between distributed processes.

Its high-level public API is:

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

It currently supports three communication patterns:

```text
request-response
        │
        └── TCPClient / TCPServer

file transfer
        │
        └── TCPFileClient / TCPFileServer

persistent bidirectional streaming
        │
        └── TCPStreamClient / TCPStreamServer
```

The transport layer knows **how to move information**, but not **what that information means**.

In particular, the TCP streaming transport manages connections and messages, while the workflow layer provides Agent registration and Agent-aware message routing.

Detailed overview:

[`transport/README.md`](transport/README.md)

Detailed TCP protocol and API:

[`transport/tcp/README.md`](transport/tcp/README.md)

---


# Workflow Layer

Directory:

```text
framework/communication/workflow/
```

The workflow layer provides two independent communication workflows:

- **Action workflow:** distributed Action claiming, local execution-state management, polling, and lifecycle synchronization.
- **Streaming workflow:** persistent bidirectional communication with Agent registration and targeted message routing.

Its public API is:

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

The responsibilities are:

| Component | Responsibility |
|---|---|
| `Coordinator` | Find and claim the next eligible authoritative Action. |
| `WorkflowHandler` | Expose authoritative Action lifecycle operations as workflow requests. |
| `WorkflowClient` | Allow an Agent to claim work and report lifecycle state remotely. |
| `AgentWorkflowHandler` | Connect a local executor to the Agent's durable workflow state. |
| `AgentPoller` | Request new work only when the Agent has no active local Action. |
| `StreamClient` | Provide Agent-side streaming, registration, and message exchange. |
| `StreamHandler` | Manage Agent registrations and route messages over persistent connections. |

The Action workflow uses authoritative and Agent-local storage to coordinate discrete distributed operations.

The streaming workflow operates independently of Action storage and lifecycle management. It uses the transport-independent `Agent` identity model together with the persistent TCP streaming transport.

An application can compose both workflows without coupling their internal responsibilities.

Detailed documentation:

[`workflow/README.md`](workflow/README.md)

---

# Authoritative Side

A minimal authoritative communication service requires:

```text
ActionStore
     │
     ▼
WorkflowHandler
     │
     ▼
TCPServer
```

Example:

```python
from framework.communication.storage import (
    ActionStore,
)

from framework.communication.transport import (
    TCPServer,
)

from framework.communication.workflow import (
    WorkflowHandler,
)


action_store = ActionStore(
    root="runtime/actions",
)

workflow_handler = WorkflowHandler(
    action_store=action_store,
)

server = TCPServer(
    handler=workflow_handler.handle,
    host="0.0.0.0",
    port=5005,
)

server.start()
```

This provides the generic authoritative workflow commands:

```text
claim_next
mark_running
mark_terminal
```

The communication framework does not create application-specific actions here.

Actions can be created by a higher-level orchestration or application layer and persisted into the authoritative `ActionStore`.

---

# Agent Side

A typical agent combines:

```text
Agent
AgentActionStore
TCPClient
WorkflowClient
AgentPoller
AgentWorkflowHandler
TCPServer
```

Conceptually:

```text
                    REMOTE AUTHORITY
                          ▲
                          │
                     TCPClient
                          ▲
                          │
                    WorkflowClient
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
      AgentActionStore            AgentPoller
             ▲
             │
     AgentWorkflowHandler
             ▲
             │
          TCPServer
             ▲
             │
        local executor
```

Example construction:

```python
from framework.communication.core import (
    Agent,
)

from framework.communication.storage import (
    AgentActionStore,
)

from framework.communication.transport import (
    TCPClient,
    TCPServer,
)

from framework.communication.workflow import (
    WorkflowClient,
    AgentWorkflowHandler,
    AgentPoller,
)


agent = Agent(
    agent_id="processing_pc_01",
    roles=["processing"],
)

local_store = AgentActionStore(
    root="runtime/processing_pc_01",
    agent=agent,
)

master_client = TCPClient(
    host="192.168.1.10",
    port=5005,
)

workflow_client = WorkflowClient(
    tcp_client=master_client,
    agent=agent,
    local_store=local_store,
)

agent_handler = AgentWorkflowHandler(
    local_store=local_store,
    workflow_client=workflow_client,
)

poller = AgentPoller(
    workflow_client=workflow_client,
    local_store=local_store,
)

local_server = TCPServer(
    handler=agent_handler.handle,
    host="127.0.0.1",
    port=6005,
)
```

The poller can then run continuously while the local server exposes workflow commands to the executor.

---

# Local Executor Interface

A local executor does not need direct access to:

- the authoritative `ActionStore`;
- the remote workflow handler;
- the polling mechanism;
- the agent's internal synchronization logic.

It can communicate with the local agent interface.

To request work:

```python
{
    "command": "consume_action",
}
```

If work is available:

```python
{
    "status": "ok",
    "trigger": True,
    "action": {
        ...
    },
}
```

If no unconsumed work is available:

```python
{
    "status": "ok",
    "trigger": False,
    "action": None,
}
```

After execution:

```python
{
    "command": "mark_terminal",
    "action_status": "completed",
}
```

or:

```python
{
    "command": "mark_terminal",
    "action_status": "failed",
}
```

or:

```python
{
    "command": "mark_terminal",
    "action_status": "cancelled",
}
```

This keeps application execution separate from distributed communication mechanics.

---

# Polling and Agent Availability

`AgentPoller` provides continuous work discovery.

Its first question is always:

```text
Does this agent already have
an active local action?
```

If yes:

```text
do not contact the authoritative
side for another action
```

If no:

```text
ask for the next eligible action
```

This produces queue-like distributed behavior:

```text
Action A → claimed by agent
Action B → remains pending

Action A executing
      │
      ▼
Action B remains pending

Action A terminal + synchronized
      │
      ▼
agent becomes available
      │
      ▼
Action B may now be claimed
```

The communication framework therefore prevents one agent from accumulating multiple active actions through normal polling.

---

# Terminal Synchronization and Retry

Distributed communication can fail after one side has already changed state.

For example:

```text
agent
  │
  │ report COMPLETED
  ▼
authoritative side
  │
  │ stores COMPLETED
  ▼
response lost
```

The authoritative side may already contain:

```text
COMPLETED
```

while the agent still contains:

```text
local_status      = completed
terminal_reported = False
```

The action therefore remains active locally.

The same terminal result can be reported again, and authoritative terminal reporting is idempotent when the requested terminal state already matches the stored terminal state.

After acknowledgement:

```text
terminal_reported = True
```

and the action becomes inactive locally.

This prevents an unacknowledged execution result from being silently replaced by new work.

---

# Running-State Synchronization

The start of execution follows:

```text
local mark_consumed()
        │
        ▼
report mark_running()
        │
        ▼
authoritative RUNNING
        │
        ▼
local mark_running_reported()
```

This means local consumption is persisted before the remote running transition is requested.

Unlike terminal reporting, the current running-state synchronization does not provide the same complete retry symmetry as terminal synchronization.

Applications should therefore treat communication interruption during the transition from local `CONSUMED` to authoritative `RUNNING` as a state that may require operational recovery.

This distinction is part of the current communication behavior and should not be assumed to have the same retry semantics as terminal reporting.

---

# File Transfer

Distributed workflows often need to exchange files in addition to action messages.

The communication framework provides generic file transfer independently from action workflow:

```text
TCPFileClient
      │
      ▼
TCPFileServer
      │
      ▼
application resolver
      │
      ▼
resolved file
```

A client can send a semantic request:

```python
{
    "operation": "download",
    "resource_id": "resource-001",
    "file": "result.json",
}
```

A higher-level resolver determines which server-side file that request represents.

The transport layer then transfers the bytes.

This separation means clients do not need to know authoritative server-local filesystem paths.

The framework also supports uploads through an independent upload resolver.

See:

[`transport/README.md`](transport/README.md)

and:

[`transport/tcp/README.md`](transport/tcp/README.md)

for the file-transfer API and protocol.

---

# Communication vs Orchestration

Communication and orchestration are related but separate concerns.

Communication answers:

```text
How is an action claimed?
How does an agent receive it?
How is execution state synchronized?
How is the terminal result reported?
```

Orchestration answers:

```text
Which action should exist?
What step comes next?
When should the next action be released?
```

The separation is:

```text
ORCHESTRATION
     │
     │ creates/releases Actions
     ▼
ActionStore
     ▲
     │
COMMUNICATION
     │
     │ claims and synchronizes Actions
     ▼
distributed agents
```

The communication framework therefore does not need to understand the larger process that caused an action to exist.

---

# Communication vs Execution

The communication framework also does not execute the operation described by an action.

```text
COMMUNICATION
     │
     │ delivers Action
     ▼
EXECUTOR
     │
     │ performs operation
     ▼
COMMUNICATION
     │
     │ synchronizes result
     ▼
AUTHORITATIVE STATE
```

This boundary is important because execution technologies can change without changing the distributed communication protocol.

---

# Communication vs File Semantics

The file transport layer does not determine what a file means.

```text
semantic request
      │
      ▼
application resolver
      │
      ▼
authoritative file path
      │
      ▼
TCP file transport
      │
      ▼
remote destination
```

Therefore application-specific concepts remain outside the generic communication framework.

---

# Which Package Should I Use?

For defining an action or agent:

```python
from framework.communication.core import ...
```

See:

[`core/README.md`](core/README.md)

For authoritative or agent-local action persistence:

```python
from framework.communication.storage import ...
```

See:

[`storage/README.md`](storage/README.md)

For TCP messages or file transfer:

```python
from framework.communication.transport import ...
```

See:

[`transport/README.md`](transport/README.md)

For distributed claiming, polling, consumption, and lifecycle synchronization:

```python
from framework.communication.workflow import ...
```

See:

[`workflow/README.md`](workflow/README.md)

For low-level TCP framing and file-streaming details:

```python
from framework.communication.transport.tcp import ...
```

See:

[`transport/tcp/README.md`](transport/tcp/README.md)

---

# Import Structure

`framework.communication` itself currently does not re-export the objects from its subpackages.

Use explicit imports from the relevant layer:

```python
from framework.communication.core import (
    Action,
    ActionStatus,
    Agent,
)

from framework.communication.storage import (
    ActionStore,
    AgentActionStore,
)

from framework.communication.transport import (
    TCPClient,
    TCPServer,
    TCPFileClient,
    TCPFileServer,
    TCPStreamClient,
    TCPStreamServer,
)

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

This keeps the architectural layer being used visible in application code.

---

# Public API Overview

| Layer | Public objects | Main responsibility |
|---|---|---|
| `core` | `Action`, `ActionStatus`, `Agent` | Distributed data models and capability identity. |
| `storage` | `ActionStore`, `AgentActionStore` | Authoritative and agent-local durable state. |
| `transport` | `TCPClient`, `TCPServer`, `TCPFileClient`, `TCPFileServer`, `TCPStreamClient`, `TCPStreamServer` | Request-response, file transfer, and persistent bidirectional streaming. |
| `workflow` | `Coordinator`, `WorkflowHandler`, `WorkflowClient`, `AgentWorkflowHandler`, `AgentPoller`, `StreamClient`, `StreamHandler` | Distributed Action lifecycle coordination and Agent-aware streaming. |

For exact constructors, methods, validation rules, protocols, and detailed examples, continue to the README of the relevant subpackage.

---

# Recommended Reading Order

For a new developer, the recommended order is:

```text
communication/README.md
        │
        ├──► core/README.md
        │
        ├──► storage/README.md
        │
        ├──► transport/README.md
        │        │
        │        └──► tcp/README.md
        │
        └──► workflow/README.md
```

Start here to understand the complete distributed communication model.

Then use the lower-level documentation as API reference while implementing or debugging individual components.