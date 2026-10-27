"""
eWoodX thickness reference plate detection.

Detects colored circular thickness plates within a workspace.
Optionally validates physical plate diameter using a pixel-to-mm
homography.

No camera, network, or persistence dependencies.
"""

import cv2
import numpy as np

from projects.ewoodx.config import (
    THICKNESS_PLATES,
    THICKNESS_PLATE_DIAMETER_MM,
    THICKNESS_PLATE_MIN_CIRCULARITY,
    THICKNESS_PLATE_DIAMETER_TOLERANCE,
)


class ThicknessPlateDetector:
    """Detect the highest-scoring valid colored thickness plate."""

    def __init__(
        self,
        plates=None,
        diameter_mm=THICKNESS_PLATE_DIAMETER_MM,
        min_circularity=THICKNESS_PLATE_MIN_CIRCULARITY,
        diameter_tolerance=THICKNESS_PLATE_DIAMETER_TOLERANCE,
        verbose=False,
    ):
        self.plates = THICKNESS_PLATES if plates is None else plates
        self.diameter_mm = float(diameter_mm)
        self.min_circularity = float(min_circularity)
        self.diameter_tolerance = float(diameter_tolerance)
        self.verbose = verbose

    def detect(
        self,
        image: np.ndarray,
        homography: np.ndarray | None = None,
        workspace_mask: np.ndarray | None = None,
    ) -> dict | None:
        """
        Detect a thickness plate.

        Parameters
        ----------
        image:
            Undistorted BGR image.

        homography:
            Optional 3x3 pixel-to-mm homography.

        workspace_mask:
            Optional uint8 binary workspace mask.

        Returns
        -------
        dict or None:
            color_name
            thickness_mm
            center_px
            radius_px
            diameter_mm
            display_color_bgr
            circularity
            mask
        """

        if not self.plates:
            return None

        hsv = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2HSV,
        )

        best = None
        best_score = -1.0

        for color_name, plate_config in self.plates.items():

            thickness_mm = float(
                plate_config["thickness_mm"]
            )

            hsv_ranges = plate_config.get(
                "hsv_ranges",
                [],
            )

            display_color = plate_config.get(
                "display_color_bgr",
                (255, 255, 255),
            )

            # --------------------------------------------
            # HSV color segmentation
            # --------------------------------------------

            combined_mask = np.zeros(
                image.shape[:2],
                dtype=np.uint8,
            )

            for hsv_range in hsv_ranges:

                lower = np.array(
                    hsv_range["lower"],
                    dtype=np.uint8,
                )

                upper = np.array(
                    hsv_range["upper"],
                    dtype=np.uint8,
                )

                color_mask = cv2.inRange(
                    hsv,
                    lower,
                    upper,
                )

                combined_mask = cv2.bitwise_or(
                    combined_mask,
                    color_mask,
                )

            # --------------------------------------------
            # Workspace restriction
            # --------------------------------------------

            if workspace_mask is not None:

                combined_mask = cv2.bitwise_and(
                    combined_mask,
                    workspace_mask,
                )

            # --------------------------------------------
            # Morphological cleaning
            # --------------------------------------------

            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (7, 7),
            )

            combined_mask = cv2.morphologyEx(
                combined_mask,
                cv2.MORPH_CLOSE,
                kernel,
            )

            combined_mask = cv2.morphologyEx(
                combined_mask,
                cv2.MORPH_OPEN,
                kernel,
            )

            # --------------------------------------------
            # Find circular candidates
            # --------------------------------------------

            contours, _ = cv2.findContours(
                combined_mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )

            for contour in contours:

                area = cv2.contourArea(
                    contour
                )

                if area < 500:
                    continue

                perimeter = cv2.arcLength(
                    contour,
                    True,
                )

                if perimeter <= 0:
                    continue

                circularity = (
                    4.0 * np.pi * area
                ) / (perimeter * perimeter)

                if circularity < self.min_circularity:
                    continue

                (cx, cy), radius = (
                    cv2.minEnclosingCircle(contour)
                )

                cx = int(round(cx))
                cy = int(round(cy))
                radius = int(round(radius))

                if radius < 5:
                    continue

                # ----------------------------------------
                # Optional physical diameter validation
                # ----------------------------------------

                measured_diameter_mm = 0.0

                if homography is not None:

                    point_left = np.array(
                        [[cx - radius, cy]],
                        dtype=np.float32,
                    ).reshape(-1, 1, 2)

                    point_right = np.array(
                        [[cx + radius, cy]],
                        dtype=np.float32,
                    ).reshape(-1, 1, 2)

                    mm_left = cv2.perspectiveTransform(
                        point_left,
                        homography,
                    ).reshape(-1, 2)[0]

                    mm_right = cv2.perspectiveTransform(
                        point_right,
                        homography,
                    ).reshape(-1, 2)[0]

                    measured_diameter_mm = float(
                        np.linalg.norm(
                            mm_right - mm_left
                        )
                    )

                    lower_limit = (
                        self.diameter_mm
                        * (1.0 - self.diameter_tolerance)
                    )

                    upper_limit = (
                        self.diameter_mm
                        * (1.0 + self.diameter_tolerance)
                    )

                    if not (
                        lower_limit
                        <= measured_diameter_mm
                        <= upper_limit
                    ):

                        if self.verbose:
                            print(
                                "[ThicknessPlate] Rejected "
                                f"{color_name}: diameter "
                                f"{measured_diameter_mm:.1f} mm"
                            )

                        continue

                # ----------------------------------------
                # Candidate scoring
                # ----------------------------------------

                score = area * circularity

                if score <= best_score:
                    continue

                best_score = score

                plate_mask = np.zeros(
                    image.shape[:2],
                    dtype=np.uint8,
                )

                cv2.drawContours(
                    plate_mask,
                    [contour],
                    -1,
                    255,
                    thickness=cv2.FILLED,
                )

                best = {
                    "color_name": color_name,
                    "thickness_mm": thickness_mm,
                    "center_px": (cx, cy),
                    "radius_px": radius,
                    "diameter_mm": round(
                        measured_diameter_mm,
                        1,
                    ),
                    "display_color_bgr": display_color,
                    "circularity": round(
                        circularity,
                        3,
                    ),
                    "mask": plate_mask,
                }

        if best is not None and self.verbose:

            print(
                "[ThicknessPlate] Detected: "
                f"{best['color_name']} "
                f"({best['thickness_mm']:.0f} mm), "
                f"diameter={best['diameter_mm']:.1f} mm, "
                f"circularity={best['circularity']:.2f}"
            )

        return best