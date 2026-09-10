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

ARDUCAM_IMAGE_WIDTH = 1280
ARDUCAM_IMAGE_HEIGHT = 720


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

# ---------------------------------------------------------------------
# Arducam extrinsic calibration
# ---------------------------------------------------------------------

ARDUCAM_ARUCO_DICTIONARY = (
    "DICT_4X4_50"
)

ARDUCAM_MARKER_SIZE_MM = (
    100.0
)

ARDUCAM_MARKER_WORLD_POSITIONS_MM = {
    1: (0.0, 0.0),
    0: (776.0, 0.0),
    2: (0.0, 440.0),
    3: (776.0, 440.0),
}

ARDUCAM_MARKER_OUTER_CORNERS = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
}

# ---------------------------------------------------------------------
# eWoodX sensing workspace
# ---------------------------------------------------------------------

EWOODX_SENSING_WORKSPACE_LAYOUT = {
    "images": (
        "sensing/images"
    ),
    "masks": (
        "sensing/masks"
    ),
    "overlays": (
        "sensing/overlays"
    ),
    "measurements": (
        "sensing/measurements"
    ),
}


# ---------------------------------------------------------------------
# eWoodX timber segmentation
# ---------------------------------------------------------------------

TIMBER_MIN_CONTOUR_AREA_PX = (
    5000
)

TIMBER_CONTOUR_APPROX_FACTOR = (
    0.004
)

TIMBER_THICKNESS_MM = (
    0.0
)


# ---------------------------------------------------------------------
# Arducam measurement setup
# ---------------------------------------------------------------------

ARDUCAM_CAMERA_HEIGHT_MM = (
    1750.0
)