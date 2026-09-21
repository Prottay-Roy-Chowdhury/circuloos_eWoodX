"""eWoodX workspace configuration."""

from pathlib import Path


# ---------------------------------------------------------------------
# eWoodX project paths
# ---------------------------------------------------------------------

EWOODX_PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

EWOODX_REPOSITORY_ROOT = (
    EWOODX_PROJECT_ROOT
    .parents[1]
)


# ---------------------------------------------------------------------
# eWoodX workspace
# ---------------------------------------------------------------------

EWOODX_WORKSPACE_LAYOUT = {
    "index": "index",
    "agents_runtime": "agents_runtime",
    "sensing": "sensing",
    "design": "design",
    "robot_control": "robot_control",
}


# ---------------------------------------------------------------------
# eWoodX workspace directories
# ---------------------------------------------------------------------

AGENTS_RUNTIME_DIRECTORY = "agents_runtime"


# ---------------------------------------------------------------------
# eWoodX domains
# ---------------------------------------------------------------------

SENSING_DOMAIN = "sensing"
DESIGN_DOMAIN = "design"
ROBOT_CONTROL_DOMAIN = "robot_control"


# ---------------------------------------------------------------------
# eWoodX entry naming
# ---------------------------------------------------------------------

ENTRY_NAME_PREFIX = "day"
ENTRY_DATE_FORMAT = "%Y%m%d"