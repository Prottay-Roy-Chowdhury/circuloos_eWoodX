from pathlib import Path


# ---------------------------------------------------------------------
# eWoodX project paths
# ---------------------------------------------------------------------

EWOODX_PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

CALIBRATION_ROOT = (
    EWOODX_PROJECT_ROOT
    / "calibration_data"
)


# ---------------------------------------------------------------------
# Arducam acquisition
# ---------------------------------------------------------------------

ARDUCAM_CAMERA_INDEX = 1

ARDUCAM_IMAGE_WIDTH = 5472
ARDUCAM_IMAGE_HEIGHT = 3648


# ---------------------------------------------------------------------
# Arducam intrinsic calibration
# ---------------------------------------------------------------------

ARDUCAM_CHECKERBOARD_INNER_CORNERS = (
    13,
    8,
)

ARDUCAM_CHECKERBOARD_SQUARE_SIZE_MM = (
    20.0
)


# ---------------------------------------------------------------------
# Arducam calibration directory layout
# ---------------------------------------------------------------------

ARDUCAM_CALIBRATION_LAYOUT = {
    "intrinsic": (
        "arducam/intrinsic"
    ),
    "intrinsic_images": (
        "arducam/intrinsic/images"
    ),
    "extrinsic": (
        "arducam/extrinsic"
    ),
    "extrinsic_images": (
        "arducam/extrinsic/images"
    ),
}