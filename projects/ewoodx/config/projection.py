"""eWoodX projection configuration."""

import argparse
import os

from projects.ewoodx.config.workspace import (
    EWOODX_REPOSITORY_ROOT,
)

from projects.ewoodx.config.sensing import (
    TABLE_WIDTH_MM,
    TABLE_HEIGHT_MM,
)


# ---------------------------------------------------------------------
# Projector physical setup
# ---------------------------------------------------------------------

PROJECTOR_HEIGHT_MM = (
    2300.0
)

PROJECTOR_POS_X_MM = (
    920.0
)

PROJECTOR_POS_Y_MM = (
    50.0
)


# ---------------------------------------------------------------------
# Projector display
# ---------------------------------------------------------------------

PROJECTOR_WIDTH = (
    1280
)

PROJECTOR_HEIGHT = (
    800
)

PROJECTOR_SCREEN_ORIGIN_X = (
    2560
)

PROJECTOR_SCREEN_ORIGIN_Y = (
    0
)

# ---------------------------------------------------------------------
# Projector calibration
# ---------------------------------------------------------------------

PROJECTOR_CALIBRATION_MODE = (
    "manual"
)


# ---------------------------------------------------------------------
# Projector environment
# ---------------------------------------------------------------------

_EWOODX_ENV = os.getenv(
    "EWOODX_ENV",
    "development",
)

if _EWOODX_ENV == "development":

    PROJECTOR_WIDTH = (
        1280
    )

    PROJECTOR_HEIGHT = (
        800
    )

elif _EWOODX_ENV == "production":

    PROJECTOR_WIDTH = (
        1920
    )

    PROJECTOR_HEIGHT = (
        1080
    )


# ---------------------------------------------------------------------
# Projector command-line overrides
# ---------------------------------------------------------------------

def _override_from_cli() -> None:

    parser = argparse.ArgumentParser(
        add_help=False,
    )

    parser.add_argument(
        "--proj_width",
        type=int,
    )

    parser.add_argument(
        "--proj_height",
        type=int,
    )

    parser.add_argument(
        "--proj_x",
        type=int,
    )

    parser.add_argument(
        "--proj_y",
        type=int,
    )

    args, _ = (
        parser.parse_known_args()
    )

    if args.proj_width is not None:

        globals()[
            "PROJECTOR_WIDTH"
        ] = args.proj_width

    if args.proj_height is not None:

        globals()[
            "PROJECTOR_HEIGHT"
        ] = args.proj_height

    if args.proj_x is not None:

        globals()[
            "PROJECTOR_SCREEN_ORIGIN_X"
        ] = args.proj_x

    if args.proj_y is not None:

        globals()[
            "PROJECTOR_SCREEN_ORIGIN_Y"
        ] = args.proj_y


_override_from_cli()

del _override_from_cli


# ---------------------------------------------------------------------
# Projector fine adjustment
# ---------------------------------------------------------------------

PROJECTOR_OFFSET_X_MM = (
    0.0
)

PROJECTOR_OFFSET_Y_MM = (
    0.0
)

# ---------------------------------------------------------------------
# Projector calibration directory layout
# ---------------------------------------------------------------------

PROJECTOR_CALIBRATION_LAYOUT = {
    "manual": (
        "projector/manual"
    ),
    "automatic": (
        "projector/automatic"
    ),
}

# ---------------------------------------------------------------------
# Temporary projector compatibility directory
# ---------------------------------------------------------------------
#
# DEVELOPMENT NOTE:
#
# This directory is a temporary compatibility bridge for the current
# projector workflow.
#
# Every successfully sensed Timber entity also writes a copy of its
# measurements JSON here so the projector can continue using the
# reference workflow of locating the latest:
#
#     timber_*_measurement.json
#
# The persistent Timber entity remains the authoritative source.
#
# This temporary directory should be removed or replaced once the
# design/data workflow retrieves the required entity data through the
# database / distributed communication workflow.
# ---------------------------------------------------------------------

PROJECTOR_RUNTIME_ROOT = (
    EWOODX_REPOSITORY_ROOT
    / "projector_runtime"
)