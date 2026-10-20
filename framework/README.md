# Framework

The `framework` package provides reusable software infrastructure for organizing, coordinating, communicating, persisting, and executing distributed physical-digital workflows.

It is designed around a separation between:

```text
generic reusable capabilities
            │
            ▼
        framework/
```

and:

```text
application-specific behavior
            │
            ▼
        project layer
```

The framework is **under continuous development**.

It should not be interpreted as a finished or fixed software architecture. The current structure represents the capabilities that have been implemented, tested, and generalized so far. New capabilities, equipment integrations, execution patterns, and framework areas are expected to be added as development continues.

## Framework Architecture

The diagram below provides an overview of the current framework architecture and its relationship with the application/project layer and physical or external systems.

![Framework Architecture](./framework_architecture.png)

The framework is organized around a central orchestration and communication cycle, supported by reusable operational capabilities and persistent data organization. The application/project layer composes these capabilities into domain-specific workflows, while physical and external systems provide the execution environment, equipment, and feedback.

The architecture represents the **current development state** of the framework and is expected to evolve as additional capabilities and integrations are developed.

The current implemented framework is centered around four areas:

```text
framework/
├── communication/
├── orchestration/
├── workspace/
└── sensing/
```

Two additional top-level areas currently exist as development placeholders:

```text
framework/
├── design/
└── robot_control/
```

These placeholders indicate intended areas of continued development but do not currently define substantive framework APIs.

---

# Purpose

The framework provides reusable infrastructure for applications that combine:

```text
physical equipment
distributed computers
persistent data
application operations
workflow coordination
```

without forcing those concerns into one monolithic application.

The central idea is to separate responsibilities:

```text
                    APPLICATION
                        │
                        │ composes
                        ▼
              ┌───────────────────┐
              │     FRAMEWORK     │
              └───────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
 communication     orchestration      workspace
        │               │               │
        │               │               │
        └───────────────┼───────────────┘
                        │
                        ▼
                     sensing
                        │
                        ▼
                physical equipment
```

Each framework area solves a different class of problems.

The application layer remains responsible for composing those capabilities into domain-specific workflows.

---

# Development Status

The framework is an **active development framework**, not a finalized software product.

The current architecture has emerged incrementally from tested application requirements and is expected to continue evolving.

The development approach is:

```text
real application requirement
        │
        ▼
working implementation
        │
        ▼
testing and validation
        │
        ▼
identify reusable behavior
        │
        ▼
move/generalize into framework
        │
        ▼
document established contract
```

rather than:

```text
design complete framework upfront
        │
        ▼
force applications into it
```

This means that different areas of the framework are currently at different levels of maturity.

---

# Current Framework Areas

| Area | Current status | Primary responsibility |
|---|---|---|
| `communication` | Implemented and tested | Distributed Actions and Agents, lifecycle synchronization, request-response communication, file transfer, and persistent Agent-aware streaming. |
| `orchestration` | Implemented and tested | Ordered workflow definitions and controlled action release. |
| `workspace` | Implemented and tested | Persistent workspace organization and optional indexed entity management. |
| `sensing` | Implemented and evolving | Reusable sensing-equipment acquisition and calibration capabilities. |
| `design` | Placeholder / future development | No substantive generic API established yet. |
| `robot_control` | Placeholder / future development | No substantive generic API established yet. |

The presence of a package does not imply that its final architecture has already been established.

In particular:

```text
implemented
    ≠ finished

documented
    ≠ frozen

placeholder
    ≠ predefined final architecture
```

---

# Current Structure

The current framework structure is:

```text
framework/
│
├── communication/
│   ├── core/
│   ├── storage/
│   ├── transport/
│   │   └── tcp/
│   └── workflow/
│
├── orchestration/
│
├── workspace/
│
├── sensing/
│   └── cameras/
│       ├── arducam/
│       └── webcam_angetube/
│
├── design/
│
├── robot_control/
│
└── test_files/
```

The detailed documentation follows the same hierarchy.

---

# Architectural Principle

The framework is organized around **responsibility boundaries** rather than around one centralized manager.

A simplified view is:

```text
ORCHESTRATION
    │
    │ decides what action becomes available
    ▼
COMMUNICATION
    │
    │ distributes and synchronizes execution
    ▼
APPLICATION OPERATION
    │
    ├──────────────┐
    ▼              ▼
SENSING         WORKSPACE
    │              │
    ▼              ▼
equipment       persistent data
```

The application operation remains the composition point.

For example, an application operation may:

```text
receive distributed action
        │
        ▼
use sensing equipment
        │
        ▼
interpret result
        │
        ▼
persist application data
```

The framework does not require the sensing package itself to understand distributed actions or the communication package to understand sensor hardware.

---

# Separation of Generic and Application Logic

A central framework boundary is:

```text
FRAMEWORK
    │
    ├── reusable data structures
    ├── reusable lifecycle behavior
    ├── reusable persistence mechanisms
    ├── reusable transport
    ├── reusable orchestration mechanics
    └── reusable equipment capabilities
```

versus:

```text
APPLICATION
    │
    ├── domain-specific actions
    ├── workflow definitions
    ├── object semantics
    ├── workspace layout choices
    ├── entity schemas
    ├── equipment selection
    ├── measurement logic
    ├── business / research rules
    └── application-specific operations
```

The framework should provide mechanisms.

The application should provide meaning.

---

# Communication

[`communication/README.md`](./communication/README.md)

The communication framework provides the distributed execution infrastructure.

Its current internal structure is:

```text
communication/
├── core/
├── storage/
├── transport/
│   └── tcp/
└── workflow/
```

Conceptually:

```text
Action + Agent
      │
      ▼
persistent lifecycle state
      │
      ▼
transport
      │
      ▼
distributed workflow protocol
```

The communication framework currently supports:

- generic actions;
- generic agents and roles;
- action claiming;
- master-side authoritative action persistence;
- agent-local durable execution state;
- action consumption;
- RUNNING synchronization;
- terminal-state synchronization;
- agent polling;
- TCP request/response communication;
- generic TCP file transfer;
- persistent bidirectional TCP JSON streaming;
- Agent-aware streaming with registration, acknowledgement, and targeted messaging;

- semantic file-resolution boundaries.


The communication framework provides two independent workflow models:

- **Action workflow:** coordinates distributed execution through Action claiming, polling, local persistence, and lifecycle synchronization.
- **Streaming workflow:** supports persistent bidirectional message exchange between registered Agents and a coordinating server.

Both models use the generic communication transport and Agent identity components. The streaming workflow does not depend on Action persistence or lifecycle state.

The detailed implementations are documented in the [Communication Workflow README](communication/workflow/README.md).


---

# Distributed Action Lifecycle

The current distributed action lifecycle is:

```text
PENDING
   │
   │ claim
   ▼
CLAIMED
   │
   │ local executor consumes
   ▼
consumed locally
   │
   │ master accepts execution start
   ▼
RUNNING
   │
   │ execution finishes
   ▼
COMPLETED / FAILED / CANCELLED
   │
   │ terminal result acknowledged
   ▼
terminal synchronization complete
```

A major principle is:

> **Status ownership follows execution ownership.**

The master owns authoritative distributed action state.

The executing agent owns local execution state.

Synchronization explicitly connects those two sides.

---

# Communication Boundaries

Communication does not decide:

```text
what the application workflow means
what sensing equipment should do
what an entity represents
how a robot should move
what a design operation should calculate
```

It provides the mechanisms for distributing and synchronizing execution.

Detailed documentation:

- [`communication/README.md`](./communication/README.md)
- [`communication/core/README.md`](./communication/core/README.md)
- [`communication/storage/README.md`](./communication/storage/README.md)
- [`communication/transport/README.md`](./communication/transport/README.md)
- [`communication/transport/tcp/README.md`](./communication/transport/tcp/README.md)
- [`communication/workflow/README.md`](./communication/workflow/README.md)

---

# Orchestration

[`orchestration/README.md`](./orchestration/README.md)

The orchestration framework defines and advances ordered application workflows.

Its current public concepts are:

```text
OrchestrationStep
        │
        ▼
OrchestrationDefinition
        │
        ▼
Orchestrator
```

with:

```text
ActionDispatcher
```

providing local action-to-handler dispatch.

The current orchestration model is deliberately small.

---

# Orchestration Responsibility

Orchestration answers:

```text
What is the ordered workflow?

Which action should be released first?

When a completed action advances,
which action should be released next?
```

Conceptually:

```text
STEP 1
  │
  ▼
Action A
  │
  │ completed
  ▼
STEP 2
  │
  ▼
Action B
  │
  │ completed
  ▼
STEP 3
```

The current orchestrator releases actions into the authoritative action store.

It does not itself execute them.

---

# Orchestration and Communication

The boundary is:

```text
ORCHESTRATION
      │
      │ creates/releases Action
      ▼
ActionStore
      ▲
      │
COMMUNICATION
      │
      ├── claim
      ├── run
      └── report terminal state
```

Orchestration owns workflow progression.

Communication owns distributed execution lifecycle.

These are related but intentionally separate responsibilities.

---

# Current Orchestration Scope

The current implementation supports sequential workflow progression.

It does not currently provide generic framework mechanisms for:

```text
parallel branches
conditional branches
loops
automatic retries
rollback
failure recovery branches
workflow scheduling
automatic background advancement
```

Those capabilities should only be added when real application requirements establish their semantics.

Detailed documentation:

[`orchestration/README.md`](./orchestration/README.md)

---

# Workspace

[`workspace/README.md`](./workspace/README.md)

The workspace framework provides persistent organization for application data.

Its core hierarchy is:

```text
Workspace
    │
    ▼
Domain
    │
    ▼
Entry
```

This is the required organizational foundation.

An optional indexed entity layer can extend an Entry:

```text
Workspace
    │
    ▼
Domain
    │
    ▼
Entry
    │
    ▼
Entity
```

with workspace-wide indexed discovery through:

```text
EntityManager
      +
entities.db
```

---

# Core Workspace Model

The core persistent structure is:

```text
Workspace → Domain → Entry
```

This can support applications that organize their own:

```text
runtime state
manifests
generated files
application stores
processing outputs
```

without using entities or SQLite.

Therefore:

```text
using workspace
      ≠
using EntityManager
```

and:

```text
using workspace
      ≠
requiring SQLite
```

---

# Optional Entity Model

Applications that need persistent, individually identified objects can use:

```text
EntityManager
```

which adds:

```text
canonical entity manifests
workspace-wide registration
indexed metadata
property-based queries
availability state
claiming
```

The distinction is:

```text
Workspace → Domain → Entry
        │
        └── core organizational model
```

versus:

```text
EntityManager
        │
        └── optional indexed object model
```

This allows the same workspace framework to support both runtime-oriented and entity-oriented applications.

---

# Workspace and Application Semantics

The workspace framework does not decide:

```text
what domains should exist
what an entry represents
what entity types should exist
which metadata should be indexed
what application files should be produced
```

Those choices belong to the application.

The framework provides persistent structures and discovery mechanisms.

Detailed documentation:

[`workspace/README.md`](./workspace/README.md)

---

# Sensing

[`sensing/README.md`](./sensing/README.md)

The sensing framework provides reusable equipment-level capabilities for acquiring and calibrating physical sensing data.

Its currently implemented category is:

```text
sensing/
└── cameras/
```

with:

```text
cameras/
├── arducam/
└── webcam_angetube/
```

The sensing framework is explicitly an **ongoing development area**.

The current camera implementations are not intended to define the final limits of the sensing architecture.

---

# Sensing Responsibility

The sensing layer handles equipment-level concerns such as:

```text
equipment connection
equipment configuration
data acquisition
calibration
equipment-level preprocessing
```

while higher-level application logic handles:

```text
object interpretation
domain-specific segmentation
measurement semantics
persistent identity
workflow meaning
```

Conceptually:

```text
PHYSICAL ENVIRONMENT
        │
        ▼
SENSING EQUIPMENT
        │
        ▼
framework.sensing
        │
        ▼
equipment-level data
        │
        ▼
APPLICATION LOGIC
        │
        ▼
application information
```

---

# Current Camera Implementations

The camera layer currently includes:

```text
Arducam
Angetube webcam
```

Both provide acquisition, calibration, ArUco detection, and planar coordinate calibration, but their equipment-specific capabilities differ.

The framework deliberately does not currently impose a universal:

```text
BaseCamera
BaseSensor
SensorManager
CameraFactory
```

abstraction.

Shared abstractions should emerge only when repeated real equipment integrations establish a useful common contract.

Detailed documentation:

- [`sensing/README.md`](./sensing/README.md)
- [`sensing/cameras/README.md`](./sensing/cameras/README.md)
- [`sensing/cameras/arducam/README.md`](./sensing/cameras/arducam/README.md)
- [`sensing/cameras/webcam_angetube/README.md`](./sensing/cameras/webcam_angetube/README.md)

---

# Design

```text
framework/design/
```

currently exists as a development placeholder.

No substantive generic Design framework API has yet been established.

This is intentional.

Application-level design operations may already exist or be developed outside this package, but they should not be generalized into `framework.design` until reusable behavior and boundaries are sufficiently clear.

The intended development approach remains:

```text
real design requirement
       │
       ▼
application implementation
       │
       ▼
tested behavior
       │
       ▼
identify reusable capability
       │
       ▼
framework.design
```

Therefore this README does not currently assign responsibilities, classes, or interfaces to `framework.design` that do not yet exist.

---

# Robot Control

```text
framework/robot_control/
```

currently also exists as a development placeholder.

No substantive generic Robot Control framework API has yet been established.

Future development may introduce reusable robotic-control capabilities when actual application integrations establish their required boundaries.

Potential future work should not be interpreted as an already-defined API.

The same development principle applies:

```text
real robotic integration
       │
       ▼
working application behavior
       │
       ▼
testing
       │
       ▼
identify reusable control capability
       │
       ▼
framework.robot_control
```

Until then, the package remains intentionally minimal.

---

# Tests

```text
framework/test_files/
```

contains framework-level and integration-oriented tests for established behavior.

The current test suite covers areas including:

```text
actions and agents
agent-local state
workflow handling
agent polling
TCP communication
file transfer
terminal synchronization
full distributed action lifecycle
action dispatch
orchestration
orchestration idempotency
workspace management
domains
entries
entities
entity indexing
entity queries
entity availability
camera acquisition / calibration components
selected application-framework integrations
TCP persistent bidirectional streaming
streaming connection lifecycle and reconnection
streaming concurrency and shutdown behavior
Agent streaming registration and message routing
registration rejection and acknowledgement timeout
streaming workflow robustness and restart

```

Tests are important architectural evidence.

They establish behavioral expectations alongside the package documentation.

When changing framework behavior:

```text
implementation
      +
tests
      +
documentation
```

should remain consistent.

---

# Framework Interaction Model

The implemented areas can be combined without collapsing their responsibilities.

A representative architecture is:

```text
                   APPLICATION
                       │
                       ▼
                 ORCHESTRATION
                       │
                       │ releases
                       ▼
                     ACTION
                       │
                       ▼
                 COMMUNICATION
                       │
                       │ distributes
                       ▼
               EXECUTING OPERATION
                  │           │
                  │           │
                  ▼           ▼
              SENSING      WORKSPACE
                  │           │
                  ▼           ▼
             equipment    persistent data
```

This diagram describes responsibility flow rather than a mandatory runtime topology.

An application may use only some framework packages.

For example:

```text
workspace only
```

is valid.

```text
sensing + workspace
```

is valid.

```text
communication + orchestration
```

is valid.

```text
communication + orchestration
+ sensing + workspace
```

is also valid.

The packages are designed to be composable rather than inseparable.

---

# Example End-to-End Responsibility Flow

A distributed sensing workflow can conceptually operate as:

```text
1. Application requests a workflow
              │
              ▼
2. Orchestrator releases an Action
              │
              ▼
3. Communication makes it claimable
              │
              ▼
4. Eligible agent claims Action
              │
              ▼
5. Local executor consumes Action
              │
              ▼
6. Communication synchronizes RUNNING
              │
              ▼
7. Application operation executes
              │
              ├── uses sensing equipment
              │
              ├── interprets sensor data
              │
              └── uses workspace persistence
              │
              ▼
8. Operation finishes
              │
              ▼
9. Communication synchronizes terminal state
              │
              ▼
10. Orchestration may release next step
```

Each layer remains responsible for only its part of the process.

---

# Responsibility Matrix

| Concern | Primary owner |
|---|---|
| Action representation | Communication |
| Agent identity and roles | Communication |
| Distributed action state | Communication |
| Local execution state | Communication |
| Network transport | Communication |
| Generic file transfer | Communication |
| Workflow structure | Orchestration |
| Sequential action release | Orchestration |
| Local action-to-handler dispatch | Orchestration |
| Workspace hierarchy | Workspace |
| Persistent domains and entries | Workspace |
| Optional entity identity/indexing | Workspace |
| Entity queries and availability | Workspace |
| Sensor hardware access | Sensing |
| Equipment calibration | Sensing |
| Equipment-level processing | Sensing |
| Domain-specific object meaning | Application |
| Application operations | Application |
| Application workflow definitions | Application |
| Application entity schemas | Application |
| Design-specific reusable capabilities | Ongoing development |
| Robot-control reusable capabilities | Ongoing development |

---

# Important Cross-Package Boundaries

## Orchestration is not communication

```text
orchestration
    │
    └── decides which action should exist
```

```text
communication
    │
    └── manages distributed execution
```

---

## Communication is not execution logic

```text
communication
    │
    └── delivers and synchronizes action
```

```text
application operation
    │
    └── performs the work
```

---

## Sensing is not application interpretation

```text
sensing
    │
    └── acquires/calibrates sensor data
```

```text
application
    │
    └── determines what the data means
```

---

## Workspace is not workflow

```text
workspace
    │
    └── organizes persistent data
```

```text
orchestration
    │
    └── organizes action progression
```

---

## Entity management is optional

```text
Workspace → Domain → Entry
```

is valid without:

```text
EntityManager
```

---

## Hardware implementation is not distributed lifecycle

A sensing device can be used without:

```text
Action
Agent
AgentPoller
Orchestrator
```

and the communication framework can operate without knowing anything about the physical sensing device.

---

# Framework and Project Layer

The framework is intended to remain generic.

A project/application layer can compose it:

```text
PROJECT / APPLICATION
        │
        ├── configuration
        ├── entrypoints
        ├── operations
        ├── agents
        ├── workflow definitions
        └── domain semantics
        │
        ▼
FRAMEWORK
        │
        ├── communication
        ├── orchestration
        ├── workspace
        ├── sensing
        ├── future design capabilities
        └── future robot-control capabilities
```

The project layer is where generic capabilities become a specific operational system.

This boundary prevents project-specific assumptions from becoming accidental framework requirements.

---

# Framework Does Not Define One Complete Application

The framework should not be understood as a ready-made application.

It does not define:

```text
which agents must exist
which equipment must be installed
which workspace domains must exist
which workflow must run
which entities must be created
which object types must be sensed
which design software must be used
which robot must be controlled
```

Instead, it provides reusable components from which different applications can construct those decisions.

---

# Incremental Generalization

A central development principle is to generalize only what has demonstrated reuse.

The preferred process is:

```text
APPLICATION A
     │
     ▼
working behavior
     │
     ▼
APPLICATION B / another use case
     │
     ▼
repeated requirement identified
     │
     ▼
generic framework capability
```

This helps avoid abstractions that are generic in name but tied to assumptions from one application.

---

# Avoiding Premature Abstraction

The framework currently favors small explicit components over broad manager layers.

For example, the current architecture does not assume the need for a universal:

```text
FrameworkManager
ServiceManager
SensorManager
EquipmentRegistry
WorkflowServiceRegistry
UniversalDataManager
```

Such abstractions may be introduced in the future if real development demonstrates a clear need.

Until then:

```text
small explicit components
        +
clear ownership
        +
composable boundaries
```

are preferred.

---

# Continuous Development

The framework documentation describes the **current established state**, not a final specification.

As development continues, changes may include:

```text
new framework areas
new sensing categories
new equipment integrations
new communication capabilities
new orchestration patterns
new workspace capabilities
design-side reusable tools
robot-control capabilities
additional tests
refined public APIs
```

When new behavior becomes established, documentation should be updated from the inside outward:

```text
implementation
      │
      ▼
lowest-level package README
      │
      ▼
parent package README
      │
      ▼
framework README
```

This keeps higher-level documentation grounded in actual implemented components.

---

# Documentation Strategy

The documentation hierarchy mirrors the architecture.

```text
framework/README.md
      │
      ├── communication/README.md
      │      ├── core/README.md
      │      ├── storage/README.md
      │      ├── transport/README.md
      │      │      └── tcp/README.md
      │      └── workflow/README.md
      │
      ├── orchestration/README.md
      │
      ├── workspace/README.md
      │
      └── sensing/README.md
             │
             └── cameras/README.md
                    ├── arducam/README.md
                    └── webcam_angetube/README.md
```

The intended documentation depth is:

```text
framework README
    │
    └── architecture + navigation

package README
    │
    └── package responsibilities + public concepts

lowest-level README
    │
    └── detailed public API + behavior
```

This avoids duplicating detailed API documentation at every level.

---

# Where to Start

For understanding the framework as a whole, start with this README.

Then use the relevant package documentation:

### Distributed execution and networking

[`communication/README.md`](./communication/README.md)

### Workflow structure and action release

[`orchestration/README.md`](./orchestration/README.md)

### Persistent organizational data and optional entities

[`workspace/README.md`](./workspace/README.md)

### Physical sensing equipment

[`sensing/README.md`](./sensing/README.md)

### Camera equipment

[`sensing/cameras/README.md`](./sensing/cameras/README.md)

---

# Current Architectural Summary

The current framework can be summarized as:

```text
                         FRAMEWORK
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   ORCHESTRATION       COMMUNICATION        WORKSPACE
          │                  │                  │
          │                  │                  │
          │            distributed              │
          │             execution               │
          │                  │                  │
          └──────────────┐   │   ┌──────────────┘
                         ▼   ▼   ▼
                    APPLICATION LOGIC
                             │
                             ▼
                          SENSING
                             │
                             ▼
                     PHYSICAL EQUIPMENT
```

with future development areas:

```text
                         FRAMEWORK
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
            DESIGN                    ROBOT CONTROL
      ongoing development          ongoing development
```

The exact relationships will continue to evolve as those capabilities are implemented.

---

# Core Principles

The framework currently follows these principles:

1. **Keep generic framework behavior separate from application-specific semantics.**
2. **Keep responsibility ownership explicit.**
3. **Status ownership follows execution ownership.**
4. **Separate orchestration from distributed execution.**
5. **Separate equipment capabilities from application interpretation.**
6. **Keep workspace organization independent from workflow execution.**
7. **Treat indexed entity management as optional rather than mandatory.**
8. **Prefer tested concrete behavior before introducing abstractions.**
9. **Keep equipment-specific differences where they matter.**
10. **Allow framework areas to evolve independently.**
11. **Use tests as behavioral evidence.**
12. **Document established behavior from the inside outward.**
13. **Treat the framework as continuously developing rather than finalized.**

---

# Summary

The `framework` package provides a growing set of reusable capabilities for distributed physical-digital applications.

Its current substantive architecture is:

```text
framework
   │
   ├── communication
   │      └── distributed execution
   │
   ├── orchestration
   │      └── workflow progression
   │
   ├── workspace
   │      └── persistent organization
   │
   └── sensing
          └── physical data acquisition
              and calibration
```

with additional development areas:

```text
design
robot_control
```

that have not yet established substantive generic APIs.

The framework is intentionally **not in a final stage**.

Its architecture is expected to continue developing as new application requirements, sensing equipment, design workflows, robotic systems, communication patterns, and persistence requirements are implemented and tested.

The guiding development model is:

```text
REAL REQUIREMENT
      │
      ▼
IMPLEMENT
      │
      ▼
TEST
      │
      ▼
GENERALIZE
      │
      ▼
DOCUMENT
      │
      ▼
CONTINUE DEVELOPMENT
```

The framework should therefore be understood as a reusable and progressively generalized software foundation whose contracts become more mature as real implementations establish them.