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
# Angetube acquisition
# ---------------------------------------------------------------------

ANGETUBE_CAMERA_INDEX = 1

ANGETUBE_IMAGE_WIDTH = 3840
ANGETUBE_IMAGE_HEIGHT = 2160

ANGETUBE_CAMERA_FPS = 30

ANGETUBE_CAMERA_FOURCC = (
    "MJPG"
)


# ---------------------------------------------------------------------
# Angetube camera control
# ---------------------------------------------------------------------

ANGETUBE_FOCUS_MODE = (
    "manual"
)

ANGETUBE_FOCUS_VALUE = (
    390
)

ANGETUBE_EXPOSURE_MODE = (
    "auto"
)

ANGETUBE_EXPOSURE_VALUE = (
    -5
)

ANGETUBE_BRIGHTNESS = (
    24
)

ANGETUBE_CONTRAST = (
    30
)

ANGETUBE_SATURATION = (
    32
)

ANGETUBE_SHARPNESS = (
    32
)

ANGETUBE_GAIN = (
    0
)

ANGETUBE_BACKLIGHT_COMPENSATION = (
    0
)

ANGETUBE_WHITE_BALANCE_MODE = (
    "auto"
)

ANGETUBE_WHITE_BALANCE_TEMPERATURE = (
    5000
)

ANGETUBE_DIGITAL_ZOOM = (
    1.80
)


# ---------------------------------------------------------------------
# Angetube intrinsic calibration
# ---------------------------------------------------------------------

ANGETUBE_CHECKERBOARD_INNER_CORNERS = (
    13,
    8,
)

ANGETUBE_CHECKERBOARD_SQUARE_SIZE_MM = (
    20.0
)

ANGETUBE_CALIBRATION_MODEL = (
    "fisheye"
)

ANGETUBE_FISHEYE_BALANCE = (
    0.0
)

ANGETUBE_FISHEYE_FOV_SCALE = (
    1.0
)

ANGETUBE_FISHEYE_CHECK_COND = (
    True
)

ANGETUBE_FISHEYE_RECOMPUTE_EXTRINSIC = (
    True
)

ANGETUBE_FISHEYE_FIX_SKEW = (
    True
)


# ---------------------------------------------------------------------
# Angetube calibration directory layout
# ---------------------------------------------------------------------

ANGETUBE_CALIBRATION_LAYOUT = {
    "intrinsic": (
        "webcam_angetube/intrinsic"
    ),
    "intrinsic_images": (
        "webcam_angetube/intrinsic/images"
    ),
    "extrinsic": (
        "webcam_angetube/extrinsic"
    ),
    "extrinsic_images": (
        "webcam_angetube/extrinsic/images"
    ),
}


# ---------------------------------------------------------------------
# Angetube extrinsic calibration
# ---------------------------------------------------------------------

ANGETUBE_ARUCO_DICTIONARY = (
    "DICT_4X4_50"
)

ANGETUBE_MARKER_SIZE_MM = (
    100.0
)

ANGETUBE_MARKER_WORLD_POSITIONS_MM = {
    1: (0.0, 0.0),
    0: (776.0, 0.0),
    2: (0.0, 440.0),
    3: (776.0, 440.0),
}

ANGETUBE_MARKER_OUTER_CORNERS = {
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

# ---------------------------------------------------------------------
# Angetube measurement setup
# ---------------------------------------------------------------------

ANGETUBE_CAMERA_HEIGHT_MM = (
    1620.0
)