"""eWoodX single-timber segmentation.

This class deliberately preserves the current segmentation algorithm and its
three-item return contract. It does not acquire frames, calibrate cameras,
measure timber, or persist project entities.
"""

import cv2
import numpy as np

from projects.ewoodx.config import TIMBER_MIN_CONTOUR_AREA_PX


class SingleTimberSegmenter:
    """Detect the highest-scoring timber contour in an ArUco workspace."""

    def __init__(self, min_contour_area_px: int = TIMBER_MIN_CONTOUR_AREA_PX):
        self.min_contour_area_px = min_contour_area_px

    def segment(
        self,
        image: np.ndarray,
        workspace_outer_px: np.ndarray,
        markers_dict: dict,
    ):
        """Return (contour, combined_mask, corners_px), or (None, mask, None)."""
        workspace_mask = self._polygon_mask(image.shape, workspace_outer_px)

        markers_mask = np.zeros(image.shape[:2], dtype=np.uint8)
        for marker_corners in markers_dict.values():
            points = np.round(marker_corners).astype(np.int32)
            cv2.fillPoly(markers_mask, [points], 255)

        marker_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        markers_mask = cv2.dilate(markers_mask, marker_kernel)
        usable_roi = cv2.bitwise_and(workspace_mask, cv2.bitwise_not(markers_mask))

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
        roi_pixels = gray_blur[usable_roi > 0]

        if roi_pixels.size < 100:
            return None, np.zeros_like(gray), None

        otsu_threshold, _ = cv2.threshold(
            roi_pixels.reshape(-1, 1),
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        black_threshold = int(np.clip(otsu_threshold, 35, 120))

        dark_mask = np.zeros_like(gray)
        dark_mask[(gray_blur <= black_threshold) & (usable_roi > 0)] = 255

        background_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        dark_mask_closed = cv2.morphologyEx(
            dark_mask, cv2.MORPH_CLOSE, background_kernel
        )

        curtain_contours, _ = cv2.findContours(
            dark_mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        curtain_domain = np.zeros_like(gray)
        for curtain_contour in curtain_contours:
            if cv2.contourArea(curtain_contour) > 15000:
                hull = cv2.convexHull(curtain_contour)
                cv2.drawContours(
                    curtain_domain, [hull], -1, 255, thickness=cv2.FILLED
                )

        usable_area = cv2.countNonZero(usable_roi)
        curtain_area = cv2.countNonZero(curtain_domain)
        if usable_area > 0 and curtain_area < 0.25 * usable_area:
            curtain_domain = usable_roi.copy()

        timber_raw = cv2.bitwise_and(
            curtain_domain, cv2.bitwise_not(dark_mask_closed)
        )
        timber_raw = cv2.bitwise_and(timber_raw, usable_roi)

        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        timber_mask = cv2.morphologyEx(timber_raw, cv2.MORPH_CLOSE, close_kernel)
        open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        timber_mask = cv2.morphologyEx(timber_mask, cv2.MORPH_OPEN, open_kernel)

        contours, _ = cv2.findContours(
            timber_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        candidates = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_contour_area_px:
                continue
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            if hull_area <= 0:
                continue
            solidity = area / hull_area
            if solidity < 0.70:
                continue

            rect = cv2.minAreaRect(contour)
            rect_width, rect_height = rect[1]
            aspect_ratio = max(rect_width, rect_height) / max(
                min(rect_width, rect_height), 1.0
            )
            if aspect_ratio < 1.8:
                continue

            score = area * min(aspect_ratio / 4.0, 2.0) * solidity
            candidates.append((score, contour))

        if not candidates:
            return None, timber_mask, None

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_contour = candidates[0][1]
        timber_corners_px = self._get_contour_oriented_box(best_contour)
        return best_contour, timber_mask, timber_corners_px

    @staticmethod
    def _polygon_mask(shape, points):
        mask = np.zeros(shape[:2], dtype=np.uint8)
        points = np.round(np.asarray(points, dtype=np.float32)).astype(np.int32)
        cv2.fillPoly(mask, [points], 255)
        return mask

    @staticmethod
    def _order_quad(points):
        points = np.asarray(points, dtype=np.float32).reshape(4, 2)
        center = points.mean(axis=0)
        angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
        order = np.argsort(angles)
        ordered = points[order]
        sums = ordered[:, 0] + ordered[:, 1]
        first = int(np.argmin(sums))
        ordered = np.roll(ordered, -first, axis=0)
        area = cv2.contourArea(ordered.reshape(-1, 1, 2))
        if area < 0:
            ordered = ordered[::-1]
        return ordered.astype(np.float32)

    def _get_contour_oriented_box(self, contour):
        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        return self._order_quad(box)