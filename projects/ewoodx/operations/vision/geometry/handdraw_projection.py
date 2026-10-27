"""
eWoodX hand-drawn shape projection.

Projects hand-drawn shape detections from undistorted image
coordinates into workspace coordinates in millimeters.

This module has no camera, YOLO, network, or persistence
dependencies.
"""

import cv2
import numpy as np


def project_detections(
    detections,
    homography,
    scale=1.0,
    origin=(0.0, 0.0),
):
    """
    Project detected shapes into workspace millimeters.

    Parameters
    ----------
    detections : list[dict]
        A single timber's detection list, as returned by
        HanddrawDetector.detect().

    homography : numpy.ndarray
        3x3 image-pixel-to-workspace-mm homography.

    scale : float
        Parallax correction scale. Reference range: (0, 1].

    origin : tuple[float, float]
        Workspace-space origin of the parallax correction.

    Returns
    -------
    list[dict]
        Copies of the input detection dictionaries, enriched
        with projected geometry and metric dimensions.
    """

    homography = np.asarray(
        homography,
        dtype=np.float64,
    )

    if (
        homography.shape != (3, 3)
        or not np.isfinite(homography).all()
        or not 0 < scale <= 1
    ):
        raise ValueError(
            "Invalid homography or parallax scale"
        )

    projected = []

    for detection in detections:

        item = dict(detection)

        x0, y0, x1, y1 = item[
            "bbox_xyxy_px"
        ]

        # --------------------------------------------
        # 1. Bounding box and center
        # --------------------------------------------

        bbox_points_px = np.asarray(
            [
                [x0, y0],
                [x1, y0],
                [x1, y1],
                [x0, y1],
                item["center_px"],
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)

        mm_bbox = cv2.perspectiveTransform(
            bbox_points_px,
            homography,
        ).reshape(-1, 2)

        mm_bbox = (
            np.asarray(origin)
            + (
                mm_bbox - np.asarray(origin)
            ) * scale
        )

        # --------------------------------------------
        # 2. Shape polygon
        # --------------------------------------------

        shape_px = item.get(
            "shape_points_px"
        )

        if shape_px is None or len(shape_px) == 0:

            shape_px = [
                [x0, y0],
                [x1, y0],
                [x1, y1],
                [x0, y1],
            ]

        raw_shape = np.asarray(
            shape_px,
            dtype=np.float32,
        ).reshape(-1, 1, 2)

        mm_shape = cv2.perspectiveTransform(
            raw_shape,
            homography,
        ).reshape(-1, 2)

        mm_shape = (
            np.asarray(origin)
            + (
                mm_shape - np.asarray(origin)
            ) * scale
        )

        # --------------------------------------------
        # 3. Metric dimensions
        # --------------------------------------------

        width_mm = float(
            np.linalg.norm(
                mm_bbox[1] - mm_bbox[0]
            )
        )

        height_mm = float(
            np.linalg.norm(
                mm_bbox[2] - mm_bbox[1]
            )
        )

        # --------------------------------------------
        # 4. Enrich detection
        # --------------------------------------------

        item["bbox_corners_mm"] = (
            mm_bbox[:4].tolist()
        )

        item["center_mm"] = (
            mm_bbox[4].tolist()
        )

        item["shape_points_mm"] = (
            mm_shape.tolist()
        )

        item["dimensions_mm"] = {
            "width": round(width_mm, 2),
            "height": round(height_mm, 2),
            "size_str": (
                f"{width_mm:.1f}x"
                f"{height_mm:.1f}mm"
            ),
        }

        item["parallax_corrected"] = (
            scale != 1.0
        )

        projected.append(item)

    return projected