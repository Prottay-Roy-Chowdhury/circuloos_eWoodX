"""eWoodX distributed communication configuration."""

from projects.ewoodx.config.workspace import (
    EWOODX_REPOSITORY_ROOT,
)


# ---------------------------------------------------------------------
# Agent runtime
# ---------------------------------------------------------------------

AGENTS_RUNTIME_ROOT = (
    EWOODX_REPOSITORY_ROOT
    / "agents_runtime"
)


# ---------------------------------------------------------------------
# Master
# ---------------------------------------------------------------------

MASTER_HOST = "127.0.0.1"
MASTER_PORT = 5105


# ---------------------------------------------------------------------
# Sensing agent
# ---------------------------------------------------------------------

SENSING_AGENT_ID = "sensing_pc_01"

SENSING_AGENT_ROLES = [
    "sensing",
]

SENSING_AGENT_HOST = "127.0.0.1"
SENSING_AGENT_PORT = 6105

SENSING_AGENT_POLL_INTERVAL = 1.0