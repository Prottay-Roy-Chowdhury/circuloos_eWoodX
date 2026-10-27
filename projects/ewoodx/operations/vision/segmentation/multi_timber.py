"""
eWoodX multi-timber segmentation.

Responsibilities:
    - Segment multiple timber objects inside an ArUco workspace.
    - Identify external contours and internal holes.
    - Exclude detected thickness-plate candidates.
    - Produce individual timber masks and geometric descriptors.

Not responsible for:
    - Camera acquisition
    - Intrinsic/extrinsic calibration
    - Thickness-plate detection
    - Hand-drawn shape detection
    - Physical measurements
    - Entity creation or persistence

Input:
    Undistorted BGR image, workspace corners, marker detections,
    and optional plate_info.

Output:
    (detected_timbers, timber_mask)

No camera or network dependencies.
"""

import cv2
import numpy as np

from projects.ewoodx.config import (
    MULTI_TIMBER_MIN_CONTOUR_AREA_PX,
    MULTI_TIMBER_MIN_HOLE_AREA_PX,
)

class MultiTimberSegmenter:
    """
    Segment multiple timber objects on a black background.

    Preserves the reference segment_board() algorithm and
    its detection dictionary structure.
    """

    def __init__(
        self,
        min_contour_area_px: int = MULTI_TIMBER_MIN_CONTOUR_AREA_PX,
        min_hole_area_px: int = MULTI_TIMBER_MIN_HOLE_AREA_PX,
        verbose: bool = False,
    ):
        self.min_contour_area_px = min_contour_area_px
        self.min_hole_area_px = min_hole_area_px
        self.verbose = verbose

    def segment(
        self,
        image: np.ndarray,
        workspace_outer_px: np.ndarray,
        markers_dict: dict | None = None,
        plate_info: dict | None = None,
    ):
        """
        Segment all qualifying timber candidates.

        Parameters
        ----------
        image : np.ndarray
            Undistorted BGR image.

        workspace_outer_px : np.ndarray
            Four outer workspace corners in image pixels.

        markers_dict : dict or None
            Mapping of marker ID to (4, 2) corner coordinates.

        plate_info : dict or None
            Optional thickness-plate detection result.

            Expected fields:
                center_px
                radius_px
                color_name

        Returns
        -------
        detected_timbers : list[dict]
            Candidate timbers sorted by descending score.

            Each dictionary contains:
                contour
                corners_px
                holes
                mask
                area
                net_area
                aspect_ratio
                solidity
                score

        timber_mask : np.ndarray
            Combined foreground mask before candidate filtering.
        """

        # ----------------------------------------------------
        # 1. Workspace mask
        # ----------------------------------------------------

        workspace_mask = self._polygon_mask(
            image.shape,
            workspace_outer_px,
        )

        # ----------------------------------------------------
        # 2. Exclude ArUco markers
        # ----------------------------------------------------

        if markers_dict:

            markers_mask = np.zeros(
                image.shape[:2],
                dtype=np.uint8,
            )

            for marker_corners in markers_dict.values():

                points = np.round(
                    marker_corners
                ).astype(np.int32)

                cv2.fillPoly(
                    markers_mask,
                    [points],
                    255,
                )

            marker_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (15, 15),
            )

            markers_mask = cv2.dilate(
                markers_mask,
                marker_kernel,
            )

            usable_roi = cv2.bitwise_and(
                workspace_mask,
                cv2.bitwise_not(markers_mask),
            )

        else:

            usable_roi = workspace_mask

        # ----------------------------------------------------
        # 3. Grayscale and Otsu threshold
        # ----------------------------------------------------

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        gray_blur = cv2.GaussianBlur(
            gray,
            (5, 5),
            0,
        )

        roi_pixels = gray_blur[
            usable_roi > 0
        ]

        if roi_pixels.size < 100:

            if self.verbose:
                print(
                    "[MultiTimber] Usable workspace too small."
                )

            return [], np.zeros_like(gray)

        otsu_threshold, _ = cv2.threshold(
            roi_pixels.reshape(-1, 1),
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

        black_threshold = int(
            np.clip(
                otsu_threshold * 0.65,
                30,
                75,
            )
        )

        if self.verbose:

            print(
                f"[MultiTimber] Otsu threshold: "
                f"{otsu_threshold:.1f}"
            )

            print(
                f"[MultiTimber] Applied threshold: "
                f"{black_threshold}"
            )

        # ----------------------------------------------------
        # 4. Detect black curtain
        # ----------------------------------------------------

        dark_mask = np.zeros_like(gray)

        dark_mask[
            (gray_blur <= black_threshold)
            & (usable_roi > 0)
        ] = 255

        background_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (15, 15),
        )

        dark_mask_closed = cv2.morphologyEx(
            dark_mask,
            cv2.MORPH_CLOSE,
            background_kernel,
        )

        curtain_contours, _ = cv2.findContours(
            dark_mask_closed,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        curtain_domain = np.zeros_like(gray)

        for curtain_contour in curtain_contours:

            if cv2.contourArea(curtain_contour) > 15000:

                hull = cv2.convexHull(
                    curtain_contour
                )

                cv2.drawContours(
                    curtain_domain,
                    [hull],
                    -1,
                    255,
                    thickness=cv2.FILLED,
                )

        if (
            cv2.countNonZero(curtain_domain)
            < 0.25 * cv2.countNonZero(usable_roi)
        ):

            curtain_domain = usable_roi.copy()

        # note:
        # The reference implementation computes curtain_domain
        # but does not apply it to timber_raw.
        #
        # This is deliberately preserved for equivalence with
        # the reference algorithm. It can be reviewed after
        # regression testing.

        # ----------------------------------------------------
        # 5. Extract timber foreground
        # ----------------------------------------------------

        timber_raw = np.zeros_like(gray)

        timber_raw[
            (gray_blur > black_threshold)
            & (usable_roi > 0)
        ] = 255

        # ----------------------------------------------------
        # 6. Morphological cleaning
        # ----------------------------------------------------

        close_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (5, 5),
        )

        timber_mask = cv2.morphologyEx(
            timber_raw,
            cv2.MORPH_CLOSE,
            close_kernel,
        )

        open_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (7, 7),
        )

        timber_mask = cv2.morphologyEx(
            timber_mask,
            cv2.MORPH_OPEN,
            open_kernel,
        )

        # ----------------------------------------------------
        # 7. Contours and hierarchy
        # ----------------------------------------------------

        contours, hierarchy = cv2.findContours(
            timber_mask,
            cv2.RETR_CCOMP,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        if not contours or hierarchy is None:

            if self.verbose:
                print(
                    "[MultiTimber] No foreground contours."
                )

            return [], timber_mask

        candidates = []

        # ----------------------------------------------------
        # 8. Evaluate outer contours
        # ----------------------------------------------------

        for i, contour in enumerate(contours):

            # RETR_CCOMP hierarchy:
            # [next, previous, first_child, parent]
            #
            # Process only top-level contours.

            if hierarchy[0][i][3] != -1:
                continue

            area = cv2.contourArea(
                contour
            )

            if area < self.min_contour_area_px:
                continue

            hull = cv2.convexHull(
                contour
            )

            hull_area = cv2.contourArea(
                hull
            )

            if hull_area <= 0:
                continue

            solidity = area / hull_area

            if solidity < 0.50:
                continue

            rect = cv2.minAreaRect(
                contour
            )

            rect_width, rect_height = rect[1]

            aspect_ratio = (
                max(rect_width, rect_height)
                / max(
                    min(rect_width, rect_height),
                    1.0,
                )
            )

            if aspect_ratio < 1.0:
                continue

            # ------------------------------------------------
            # 9. Thickness-plate candidate exclusion
            # ------------------------------------------------

            if plate_info is not None:

                cx, cy = plate_info["center_px"]
                radius = plate_info["radius_px"]

                moments = cv2.moments(
                    contour
                )

                if moments["m00"] > 0:

                    contour_cx = (
                        moments["m10"] / moments["m00"]
                    )

                    contour_cy = (
                        moments["m01"] / moments["m00"]
                    )

                    distance = np.hypot(
                        contour_cx - cx,
                        contour_cy - cy,
                    )

                    plate_area = np.pi * (
                        radius ** 2
                    )

                    matches_plate = (
                        distance < radius * 0.85
                        and 0.25 * plate_area
                        < area
                        < 2.5 * plate_area
                        and aspect_ratio < 1.5
                    )

                    if matches_plate:

                        if self.verbose:

                            print(
                                "[MultiTimber] Ignoring "
                                "thickness-plate candidate: "
                                f"{plate_info['color_name']}"
                            )

                        continue

            # ------------------------------------------------
            # 10. Extract internal holes
            # ------------------------------------------------

            holes = []

            child_idx = hierarchy[0][i][2]

            while child_idx != -1:

                hole_contour = contours[
                    child_idx
                ]

                hole_area = cv2.contourArea(
                    hole_contour
                )

                if hole_area >= self.min_hole_area_px:

                    is_plate_hole = False

                    if plate_info is not None:

                        cx, cy = plate_info["center_px"]
                        radius = plate_info["radius_px"]

                        hole_moments = cv2.moments(
                            hole_contour
                        )

                        if hole_moments["m00"] > 0:

                            hole_cx = (
                                hole_moments["m10"]
                                / hole_moments["m00"]
                            )

                            hole_cy = (
                                hole_moments["m01"]
                                / hole_moments["m00"]
                            )

                            if (
                                np.hypot(
                                    hole_cx - cx,
                                    hole_cy - cy,
                                )
                                < radius
                            ):

                                is_plate_hole = True

                    if not is_plate_hole:

                        holes.append(
                            hole_contour
                        )

                # Next sibling hole
                child_idx = hierarchy[0][child_idx][0]

            # ------------------------------------------------
            # 11. Individual timber mask
            # ------------------------------------------------

            individual_mask = np.zeros(
                timber_mask.shape,
                dtype=np.uint8,
            )

            cv2.drawContours(
                individual_mask,
                [contour],
                -1,
                255,
                thickness=cv2.FILLED,
            )

            if holes:

                cv2.drawContours(
                    individual_mask,
                    holes,
                    -1,
                    0,
                    thickness=cv2.FILLED,
                )

            # ------------------------------------------------
            # 12. Net area
            # ------------------------------------------------

            net_area = area - sum(
                cv2.contourArea(hole)
                for hole in holes
            )

            # ------------------------------------------------
            # 13. Candidate score
            # ------------------------------------------------

            score = (
                area
                * min(
                    aspect_ratio / 4.0,
                    2.0,
                )
                * solidity
            )

            candidates.append(
                (
                    score,
                    contour,
                    area,
                    aspect_ratio,
                    solidity,
                    holes,
                    individual_mask,
                    net_area,
                )
            )

        if not candidates:

            if self.verbose:
                print(
                    "[MultiTimber] No suitable timber candidates."
                )

            return [], timber_mask

        # ----------------------------------------------------
        # 14. Sort candidates
        # ----------------------------------------------------

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        detected_timbers = []

        # ----------------------------------------------------
        # 15. Build timber detections
        # ----------------------------------------------------

        for (
            score,
            contour,
            area,
            aspect_ratio,
            solidity,
            holes,
            individual_mask,
            net_area,
        ) in candidates:

            corners_px = self._get_contour_oriented_box(
                contour
            )

            detected_timbers.append(
                {
                    "contour": contour,
                    "corners_px": corners_px,
                    "holes": holes,
                    "mask": individual_mask,
                    "area": area,
                    "net_area": net_area,
                    "aspect_ratio": aspect_ratio,
                    "solidity": solidity,
                    "score": score,
                }
            )

        if self.verbose:

            print(
                f"[MultiTimber] Detected "
                f"{len(detected_timbers)} timber(s)."
            )

        return detected_timbers, timber_mask

    # ========================================================
    # GEOMETRY HELPERS
    # ========================================================

    @staticmethod
    def _polygon_mask(shape, points):
        """Create a filled workspace polygon mask."""

        mask = np.zeros(
            shape[:2],
            dtype=np.uint8,
        )

        points = np.asarray(
            points,
            dtype=np.float32,
        )

        points = np.round(
            points
        ).astype(np.int32)

        cv2.fillPoly(
            mask,
            [points],
            255,
        )

        return mask

    @staticmethod
    def _order_quad(points):
        """Order four corners in image coordinates."""

        points = np.asarray(
            points,
            dtype=np.float32,
        ).reshape(4, 2)

        center = points.mean(axis=0)

        angles = np.arctan2(
            points[:, 1] - center[1],
            points[:, 0] - center[0],
        )

        order = np.argsort(
            angles
        )

        ordered = points[order]

        sums = (
            ordered[:, 0]
            + ordered[:, 1]
        )

        first = int(
            np.argmin(sums)
        )

        ordered = np.roll(
            ordered,
            -first,
            axis=0,
        )

        area = cv2.contourArea(
            ordered.reshape(-1, 1, 2)
        )

        if area < 0:
            ordered = ordered[::-1]

        return ordered.astype(
            np.float32
        )

    @classmethod
    def _get_contour_oriented_box(cls, contour):
        """Fit an oriented rectangle to a timber contour."""

        rect = cv2.minAreaRect(
            contour
        )

        box = cv2.boxPoints(
            rect
        )

        return cls._order_quad(
            box
        )