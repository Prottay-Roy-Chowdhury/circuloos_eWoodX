"""
eWoodX timber geometry calculation.

Common geometry calculation for single-timber and multi-timber
segmentation.

Responsibilities:
    - Pixel-to-workspace homography projection
    - Camera-height parallax compensation
    - Timber length and width
    - Gross surface area
    - Internal hole areas
    - Net surface area
    - Metric contours and corners

This module does not:
    - Perform timber segmentation
    - Perform camera calibration
    - Detect thickness plates
    - Sample timber color
    - Allocate timber IDs
    - Create or save measurements.json
    - Communicate with CIRCULOOS
"""

from __future__ import annotations

from typing import Any, Sequence

import cv2
import numpy as np


def _as_points(
    points: Any,
    name: str,
    min_points: int = 3,
) -> np.ndarray:
    """Normalize point coordinates into an Nx2 float32 array."""

    array = np.asarray(
        points,
        dtype=np.float32,
    )

    if array.size == 0:
        raise ValueError(
            f"{name} cannot be empty."
        )

    try:
        array = array.reshape(-1, 2)
    except ValueError as exc:
        raise ValueError(
            f"{name} must contain 2D coordinates."
        ) from exc

    if len(array) < min_points:
        raise ValueError(
            f"{name} must contain at least "
            f"{min_points} points."
        )

    if not np.isfinite(array).all():
        raise ValueError(
            f"{name} contains non-finite coordinates."
        )

    return array


def _validate_homography(
    homography: Any,
) -> np.ndarray:
    """Validate a pixel-to-workspace homography."""

    matrix = np.asarray(
        homography,
        dtype=np.float64,
    )

    if matrix.shape != (3, 3):
        raise ValueError(
            "homography must be a 3x3 matrix."
        )

    if not np.isfinite(matrix).all():
        raise ValueError(
            "homography contains non-finite values."
        )

    if abs(np.linalg.det(matrix)) < 1e-12:
        raise ValueError(
            "homography is singular."
        )

    return matrix


def project_points_to_mm(
    pixel_points: Any,
    homography: Any,
) -> np.ndarray:
    """
    Transform undistorted image coordinates into workspace mm.

    Parameters
    ----------
    pixel_points:
        Nx2 image coordinates.

    homography:
        3x3 image-to-workspace homography.

    Returns
    -------
    np.ndarray:
        Nx2 workspace coordinates in millimeters.
    """

    points = _as_points(
        pixel_points,
        "pixel_points",
        min_points=1,
    )

    matrix = _validate_homography(
        homography
    )

    projected = cv2.perspectiveTransform(
        points.reshape(-1, 1, 2),
        matrix,
    ).reshape(-1, 2)

    if not np.isfinite(projected).all():
        raise ValueError(
            "Homography produced invalid coordinates."
        )

    return projected.astype(
        np.float32
    )


def calculate_parallax_parameters(
    homography: Any,
    camera_matrix: Any,
    camera_height_mm: float,
    timber_thickness_mm: float,
) -> tuple[float, tuple[float, float]]:
    """
    Calculate reference-compatible parallax parameters.

    Correction:
        P_corrected = C + (P - C) * scale

    Where:
        C = projected camera optical center
        scale = (camera_height - timber_thickness)
                / camera_height

    Invalid or non-positive height/thickness combinations
    disable parallax correction, matching the reference.
    """

    camera_height_mm = float(
        camera_height_mm
    )

    timber_thickness_mm = float(
        timber_thickness_mm
    )

    if (
        not np.isfinite(camera_height_mm)
        or not np.isfinite(timber_thickness_mm)
    ):
        raise ValueError(
            "Camera height and timber thickness must be finite."
        )

    use_parallax = (
        camera_height_mm > 0
        and timber_thickness_mm > 0
        and camera_height_mm > timber_thickness_mm
    )

    if not use_parallax:
        return 1.0, (0.0, 0.0)

    if camera_matrix is None:
        raise ValueError(
            "camera_matrix is required when "
            "parallax correction is active."
        )

    intrinsic = np.asarray(
        camera_matrix,
        dtype=np.float64,
    )

    if (
        intrinsic.shape != (3, 3)
        or not np.isfinite(intrinsic).all()
    ):
        raise ValueError(
            "camera_matrix must be a finite 3x3 matrix."
        )

    cx = float(intrinsic[0, 2])
    cy = float(intrinsic[1, 2])

    center_mm = project_points_to_mm(
        [[cx, cy]],
        homography,
    )[0]

    scale = (
        camera_height_mm - timber_thickness_mm
    ) / camera_height_mm

    return (
        float(scale),
        (
            float(center_mm[0]),
            float(center_mm[1]),
        ),
    )


def apply_parallax_compensation(
    points_mm: Any,
    scale: float = 1.0,
    origin_mm: Sequence[float] = (0.0, 0.0),
) -> np.ndarray:
    """Apply parallax correction around the projected optical center."""

    points = _as_points(
        points_mm,
        "points_mm",
        min_points=1,
    )

    scale = float(scale)

    origin = np.asarray(
        origin_mm,
        dtype=np.float32,
    ).reshape(2)

    if (
        not np.isfinite(scale)
        or scale <= 0
        or scale > 1
        or not np.isfinite(origin).all()
    ):
        raise ValueError(
            "Invalid parallax scale or origin."
        )

    corrected = (
        origin
        + (points - origin) * scale
    )

    return corrected.astype(
        np.float32
    )


def approximate_contour(
    contour_px: Any,
    approximation_factor: float = 0.0,
) -> np.ndarray:
    """
    Approximate a contour using cv2.approxPolyDP.

    approximation_factor = 0 preserves the input contour.
    Otherwise:
        epsilon = approximation_factor * contour_perimeter

    The composer currently performs this operation before
    projecting the outer timber contour.
    """

    contour = _as_points(
        contour_px,
        "contour_px",
    )

    approximation_factor = float(
        approximation_factor
    )

    if (
        not np.isfinite(approximation_factor)
        or approximation_factor < 0
    ):
        raise ValueError(
            "approximation_factor must be finite and >= 0."
        )

    if approximation_factor == 0:
        return contour.copy()

    contour_cv = contour.reshape(-1, 1, 2)

    perimeter = cv2.arcLength(
        contour_cv,
        True,
    )

    epsilon = (
        approximation_factor * perimeter
    )

    approximated = cv2.approxPolyDP(
        contour_cv,
        epsilon,
        True,
    ).reshape(-1, 2)

    if len(approximated) < 3:
        raise ValueError(
            "Contour approximation produced "
            "fewer than three points."
        )

    return approximated.astype(
        np.float32
    )


def _polygon_area(
    points_mm: np.ndarray,
) -> float:
    """Calculate absolute polygon area in square millimeters."""

    return abs(
        float(
            cv2.contourArea(
                np.asarray(
                    points_mm,
                    dtype=np.float32,
                ).reshape(-1, 1, 2)
            )
        )
    )


def calculate_timber_geometry(
    corners_px: Any,
    contour_px: Any,
    homography: Any,
    camera_matrix: Any = None,
    camera_height_mm: float = 0.0,
    timber_thickness_mm: float = 0.0,
    holes_px: Sequence[Any] | None = None,
    contour_approximation_factor: float = 0.0,
    hole_approximation_factor: float = 0.0,
) -> dict[str, Any]:
    """
    Calculate the metric geometry of one timber.

    The same function works for:
        - Single timber without holes
        - Single timber with holes
        - Each timber in a multi-timber capture

    Parameters
    ----------
    corners_px:
        Four ordered corners of the timber's oriented
        bounding rectangle in undistorted image pixels.

    contour_px:
        Outer timber contour in undistorted image pixels.

    homography:
        Pixel-to-workspace-mm 3x3 homography.

    camera_matrix:
        Intrinsic camera matrix. Required for active
        parallax correction.

    camera_height_mm:
        Camera height above the workspace plane.

    timber_thickness_mm:
        Timber thickness used for parallax correction.

    holes_px:
        Optional list of inner contours.

    contour_approximation_factor:
        cv2.approxPolyDP epsilon factor for outer contour.

    hole_approximation_factor:
        cv2.approxPolyDP epsilon factor for hole contours.

    Returns
    -------
    dict:
        Reference-compatible per-timber geometry fields.
        All distances are in millimeters and areas in mm².
    """

    corners = _as_points(
        corners_px,
        "corners_px",
        min_points=4,
    )

    if len(corners) != 4:
        raise ValueError(
            "corners_px must contain exactly four points."
        )

    outer_contour = approximate_contour(
        contour_px,
        contour_approximation_factor,
    )

    hole_contours = []

    for index, hole in enumerate(
        holes_px if holes_px is not None else []
    ):
        approximated_hole = approximate_contour(
            hole,
            hole_approximation_factor,
        )

        hole_contours.append(
            approximated_hole
        )

    # ---------------------------------------------------------
    # 1. Shared parallax parameters
    # ---------------------------------------------------------

    scale, origin_mm = (
        calculate_parallax_parameters(
            homography=homography,
            camera_matrix=camera_matrix,
            camera_height_mm=camera_height_mm,
            timber_thickness_mm=timber_thickness_mm,
        )
    )

    # ---------------------------------------------------------
    # 2. Project and correct outer geometry
    # ---------------------------------------------------------

    corners_mm = project_points_to_mm(
        corners,
        homography,
    )

    corners_mm = apply_parallax_compensation(
        corners_mm,
        scale,
        origin_mm,
    )

    contour_mm = project_points_to_mm(
        outer_contour,
        homography,
    )

    contour_mm = apply_parallax_compensation(
        contour_mm,
        scale,
        origin_mm,
    )

    # ---------------------------------------------------------
    # 3. Project and correct hole geometry
    # ---------------------------------------------------------

    holes_mm = []

    for hole in hole_contours:

        hole_mm = project_points_to_mm(
            hole,
            homography,
        )

        hole_mm = apply_parallax_compensation(
            hole_mm,
            scale,
            origin_mm,
        )

        holes_mm.append(
            hole_mm
        )

    # ---------------------------------------------------------
    # 4. Timber dimensions
    # ---------------------------------------------------------

    side_lengths = []

    for index in range(4):

        next_index = (index + 1) % 4

        side_length = float(
            np.linalg.norm(
                corners_mm[next_index]
                - corners_mm[index]
            )
        )

        side_lengths.append(
            side_length
        )

    dimension_a = (
        side_lengths[0] + side_lengths[2]
    ) / 2.0

    dimension_b = (
        side_lengths[1] + side_lengths[3]
    ) / 2.0

    length_mm = max(
        dimension_a,
        dimension_b,
    )

    width_mm = min(
        dimension_a,
        dimension_b,
    )

    # ---------------------------------------------------------
    # 5. Gross, hole, and net surface areas
    # ---------------------------------------------------------

    gross_surface_area_mm2 = _polygon_area(
        contour_mm
    )

    hole_areas_mm2 = [
        _polygon_area(hole)
        for hole in holes_mm
    ]

    total_hole_area_mm2 = float(
        sum(hole_areas_mm2)
    )

    surface_area_mm2 = max(
        0.0,
        gross_surface_area_mm2
        - total_hole_area_mm2,
    )

    surface_area_cm2 = (
        surface_area_mm2 / 100.0
    )

    # ---------------------------------------------------------
    # 6. Build reference-compatible geometry result
    # ---------------------------------------------------------

    holes_serialized = [
        hole.round(2).tolist()
        for hole in holes_mm
    ]

    return {
        "length_mm": round(
            float(length_mm), 2
        ),
        "width_mm": round(
            float(width_mm), 2
        ),
        "gross_surface_area_mm2": round(
            gross_surface_area_mm2, 2
        ),
        "total_hole_area_mm2": round(
            total_hole_area_mm2, 2
        ),
        "surface_area_mm2": round(
            surface_area_mm2, 2
        ),
        "surface_area_cm2": round(
            surface_area_cm2, 2
        ),
        "side_lengths_mm": [
            round(float(value), 2)
            for value in side_lengths
        ],
        "corners_mm": (
            corners_mm.round(2).tolist()
        ),
        "contour_mm": (
            contour_mm.round(2).tolist()
        ),
        "holes_mm": holes_serialized,
        "inner_contours_mm": [
            [point[:] for point in hole]
            for hole in holes_serialized
        ],
        "hole_count": len(holes_mm),
    }