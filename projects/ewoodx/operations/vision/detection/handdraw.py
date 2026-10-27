"""
eWoodX hand-drawn shape detection.

Detects hand-drawn ellipses, rectangles, and triangles on
individual segmented timber objects using a trained YOLO model.

Responsibilities:
    - Load and run the trained YOLO model
    - Preprocess timber crops using three image variantsnum
    - Detect shapes independently for each timber
    - Reject detections outside timber or inside holes
    - Merge overlapping detections
    - Reconstruct shape polygons in image coordinates
    - Draw detection overlays

Not responsible for:
    - Camera acquisition
    - Timber segmentation
    - Camera calibration
    - Pixel-to-mm projection
    - Entity identification or persistence

Input:
    Undistorted BGR image and MultiTimberSegmenter detections.

Output:
    One list of shape detections per timber.

PyTorch and Ultralytics are imported only when the detector
is instantiated.
"""

from pathlib import Path

import cv2
import numpy as np

from projects.ewoodx.config import (
    HANDDRAW_MODEL_PATH,
    HANDDRAW_DEVICE,
    HANDDRAW_CONFIDENCE,
    HANDDRAW_IMAGE_SIZE,
    HANDDRAW_IOU,
)


DEFAULT_CLASS_NAMES = {
    0: "ellipse",
    1: "rectangle",
    2: "triangle",
}

DEFAULT_COLORS = {
    0: (0, 165, 255),
    1: (255, 0, 180),
    2: (255, 180, 0),
}


# ============================================================
# SHAPE RECONSTRUCTION
# ============================================================

def generate_shape_polygon(
    class_name,
    bbox_xyxy,
    num_ellipse_points=4,
    image=None,
):
    """
    Reconstruct a shape polygon from a YOLO bounding box.

    If an image is supplied, attempts contour-based refinement.
    Otherwise uses the bounding-box geometry.

    Returns
    -------
    points : list[list[float]]
    shape_type : str
    """

    x0, y0, x1, y1 = [
        float(v) for v in bbox_xyxy
    ]

    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    w = max(1.0, x1 - x0)
    h = max(1.0, y1 - y0)

    class_lower = str(class_name).lower()

    # --------------------------------------------------------
    # Ellipse
    # --------------------------------------------------------

    if "ellipse" in class_lower or "circle" in class_lower:

        points = None

        if image is not None:

            roi_info = _extract_shape_roi(
                image,
                bbox_xyxy,
            )

            if roi_info is not None:

                contours, px0, py0 = roi_info

                if contours:

                    largest = max(
                        contours,
                        key=cv2.contourArea,
                    )

                    if len(largest) >= 5:

                        (ecx, ecy), (major, minor), angle = (
                            cv2.fitEllipse(largest)
                        )

                        angles = np.linspace(
                            0,
                            2 * np.pi,
                            36,
                            endpoint=False,
                        )

                        angle_rad = np.deg2rad(angle)

                        cos_a = np.cos(angle_rad)
                        sin_a = np.sin(angle_rad)

                        rx = major / 2.0
                        ry = minor / 2.0

                        points = []

                        for a in angles:

                            xx = (
                                ecx
                                + rx * np.cos(a) * cos_a
                                - ry * np.sin(a) * sin_a
                            )

                            yy = (
                                ecy
                                + rx * np.cos(a) * sin_a
                                + ry * np.sin(a) * cos_a
                            )

                            points.append([
                                float(xx + px0),
                                float(yy + py0),
                            ])

        if points is None:

            rx = w / 2.0
            ry = h / 2.0

            angles = np.linspace(
                0,
                2 * np.pi,
                36,
                endpoint=False,
            )

            points = [
                [
                    float(cx + rx * np.cos(a)),
                    float(cy + ry * np.sin(a)),
                ]
                for a in angles
            ]

        return points, "ellipse"

    # --------------------------------------------------------
    # Triangle
    # --------------------------------------------------------

    elif "tri" in class_lower:

        points = None

        if image is not None:

            roi_info = _extract_shape_roi(
                image,
                bbox_xyxy,
            )

            if roi_info is not None:

                contours, px0, py0 = roi_info

                if contours:

                    largest = max(
                        contours,
                        key=cv2.contourArea,
                    )

                    epsilon = (
                        0.05
                        * cv2.arcLength(largest, True)
                    )

                    approx = cv2.approxPolyDP(
                        largest,
                        epsilon,
                        True,
                    )

                    if len(approx) == 3:

                        points = [
                            [
                                float(p[0][0] + px0),
                                float(p[0][1] + py0),
                            ]
                            for p in approx
                        ]

                    else:

                        retval, triangle = (
                            cv2.minEnclosingTriangle(largest)
                        )

                        if retval:

                            points = [
                                [
                                    float(p[0][0] + px0),
                                    float(p[0][1] + py0),
                                ]
                                for p in triangle
                            ]

        if points is None:

            points = [
                [cx, y0],
                [x1, y1],
                [x0, y1],
            ]

        return points, "triangle"

    # --------------------------------------------------------
    # Rectangle
    # --------------------------------------------------------

    else:

        points = None

        if image is not None:

            roi_info = _extract_shape_roi(
                image,
                bbox_xyxy,
            )

            if roi_info is not None:

                contours, px0, py0 = roi_info

                if contours:

                    largest = max(
                        contours,
                        key=cv2.contourArea,
                    )

                    epsilon = (
                        0.05
                        * cv2.arcLength(largest, True)
                    )

                    approx = cv2.approxPolyDP(
                        largest,
                        epsilon,
                        True,
                    )

                    if len(approx) == 4:

                        box = approx.reshape(-1, 2)

                    else:

                        rect = cv2.minAreaRect(
                            largest
                        )

                        box = cv2.boxPoints(
                            rect
                        )

                    x_sorted = box[
                        np.argsort(box[:, 0])
                    ]

                    left_points = x_sorted[:2]
                    right_points = x_sorted[2:]

                    left_points = left_points[
                        np.argsort(left_points[:, 1])
                    ]

                    right_points = right_points[
                        np.argsort(right_points[:, 1])
                    ]

                    tl, bl = left_points
                    tr, br = right_points

                    ordered_box = np.array([
                        tl,
                        tr,
                        br,
                        bl,
                    ])

                    global_box = (
                        ordered_box
                        + np.array([px0, py0])
                    )

                    points = [
                        [float(p[0]), float(p[1])]
                        for p in global_box
                    ]

        if points is None:

            points = [
                [x0, y0],
                [x1, y0],
                [x1, y1],
                [x0, y1],
            ]

        return points, "rectangle"


def _extract_shape_roi(image, bbox_xyxy):
    """
    Extract contours near a detected shape.

    Uses the same adaptive-threshold parameters as the
    reference implementation.
    """

    x0, y0, x1, y1 = [
        float(v) for v in bbox_xyxy
    ]

    pad = 10

    px0 = max(0, int(x0) - pad)
    py0 = max(0, int(y0) - pad)

    px1 = min(
        image.shape[1],
        int(x1) + pad,
    )

    py1 = min(
        image.shape[0],
        int(y1) + pad,
    )

    if px1 <= px0 or py1 <= py0:
        return None

    roi = image[
        py0:py1,
        px0:px1,
    ].copy()

    gray = cv2.cvtColor(
        roi,
        cv2.COLOR_BGR2GRAY,
    )

    adaptive = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        8,
    )

    contours, _ = cv2.findContours(
        adaptive,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    return contours, px0, py0


# ============================================================
# YOLO HAND-DRAWN SHAPE DETECTOR
# ============================================================

class HanddrawDetector:
    """
    Detect hand-drawn shapes independently for each timber.

    The detection output follows the reference implementation.
    """

    def __init__(
        self,
        model_path=HANDDRAW_MODEL_PATH,
        device=HANDDRAW_DEVICE,
        confidence=HANDDRAW_CONFIDENCE,
        image_size=HANDDRAW_IMAGE_SIZE,
        iou=HANDDRAW_IOU,
    ):

        path = Path(
            model_path
        ).expanduser().resolve()

        if not path.is_file():

            raise FileNotFoundError(
                f"Trained hand-drawing model not found: {path}"
            )

        if (
            not 0 < confidence <= 1
            or not 0 < iou <= 1
            or image_size < 32
        ):

            raise ValueError(
                "Invalid YOLO confidence, IoU, or image size."
            )

        try:

            import torch
            from ultralytics import YOLO

        except ImportError as exc:

            raise RuntimeError(
                "HanddrawDetector requires "
                "PyTorch and Ultralytics."
            ) from exc

        if (
            str(device) != "cpu"
            and not torch.cuda.is_available()
        ):

            raise RuntimeError(
                "CUDA unavailable. "
                "Use a GPU-enabled environment or device='cpu'."
            )

        self.model_path = str(path)

        self.model = YOLO(
            str(path),
            task="detect",
        )

        names = self.model.names

        if isinstance(names, list):

            actual_names = dict(
                enumerate(names)
            )

        elif isinstance(names, dict):

            actual_names = names

        else:

            actual_names = DEFAULT_CLASS_NAMES

        self.class_names = {
            int(k): str(v)
            for k, v in actual_names.items()
        }

        self.device = device
        self.confidence = float(confidence)
        self.image_size = int(image_size)
        self.iou = float(iou)

        # Reference model warm-up
        self.model.predict(
            np.full(
                (image_size, image_size, 3),
                245,
                np.uint8,
            ),
            device=device,
            imgsz=image_size,
            verbose=False,
        )

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def set_confidence(self, confidence):

        self.confidence = max(
            0.01,
            min(0.99, float(confidence)),
        )

    # ========================================================
    # DETECTION FILTERS
    # ========================================================

    @staticmethod
    def _is_edge_detection(
        bx0,
        by0,
        bx1,
        by1,
        crop_width,
        crop_height,
        edge_margin_frac=0.08,
    ):

        margin_x = (
            crop_width * edge_margin_frac
        )

        margin_y = (
            crop_height * edge_margin_frac
        )

        return (
            bx0 < margin_x
            or bx1 > crop_width - margin_x
            or by0 < margin_y
            or by1 > crop_height - margin_y
        )

    # ========================================================
    # PREPROCESSING
    # ========================================================

    @staticmethod
    def _preprocess_adaptive_threshold(
        masked_crop,
        crop_mask,
    ):

        gray = cv2.cvtColor(
            masked_crop,
            cv2.COLOR_BGR2GRAY,
        )

        gray_masked = gray.copy()

        gray_masked[
            crop_mask == 0
        ] = 200

        adaptive = cv2.adaptiveThreshold(
            gray_masked,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            8,
        )

        result = cv2.cvtColor(
            adaptive,
            cv2.COLOR_GRAY2BGR,
        )

        result[
            crop_mask == 0
        ] = [180, 180, 180]

        return result

    @staticmethod
    def _preprocess_unsharp_clahe(
        masked_crop,
        crop_mask,
    ):

        blur = cv2.GaussianBlur(
            masked_crop,
            (0, 0),
            3,
        )

        unsharp = cv2.addWeighted(
            masked_crop,
            2.0,
            blur,
            -1.0,
            0,
        )

        lab = cv2.cvtColor(
            unsharp,
            cv2.COLOR_BGR2LAB,
        )

        l_chan, a_chan, b_chan = cv2.split(
            lab
        )

        clahe = cv2.createCLAHE(
            clipLimit=3.0,
            tileGridSize=(8, 8),
        )

        enhanced_l = clahe.apply(
            l_chan
        )

        result = cv2.cvtColor(
            cv2.merge(
                (enhanced_l, a_chan, b_chan)
            ),
            cv2.COLOR_LAB2BGR,
        )

        result[
            crop_mask == 0
        ] = [180, 180, 180]

        return result

    @staticmethod
    def _preprocess_clahe(
        masked_crop,
        crop_mask,
    ):

        lab = cv2.cvtColor(
            masked_crop,
            cv2.COLOR_BGR2LAB,
        )

        l_chan, a_chan, b_chan = cv2.split(
            lab
        )

        clahe = cv2.createCLAHE(
            clipLimit=3.0,
            tileGridSize=(8, 8),
        )

        enhanced_l = clahe.apply(
            l_chan
        )

        result = cv2.cvtColor(
            cv2.merge(
                (enhanced_l, a_chan, b_chan)
            ),
            cv2.COLOR_LAB2BGR,
        )

        result[
            crop_mask == 0
        ] = [180, 180, 180]

        return result

    # ========================================================
    # YOLO INFERENCE
    # ========================================================

    def _run_inference(
        self,
        image_bgr,
        imgsz=640,
    ):

        results = self.model.predict(
            image_bgr,
            device=self.device,
            conf=self.confidence,
            iou=self.iou,
            imgsz=imgsz,
            agnostic_nms=True,
            verbose=False,
        )[0]

        candidates = []

        if (
            results.boxes is not None
            and len(results.boxes) > 0
        ):

            rows = (
                results.boxes.data
                .detach()
                .cpu()
                .numpy()
            )

            for row in rows:

                bx0, by0, bx1, by1, score, cls = map(
                    float,
                    row[:6],
                )

                candidates.append(
                    (
                        bx0,
                        by0,
                        bx1,
                        by1,
                        score,
                        int(cls),
                    )
                )

        return candidates

    def _predict_crop(
        self,
        masked_crop,
        contour_shifted,
        crop_mask=None,
    ):
        """
        Run three preprocessing variants and combine
        their raw YOLO detections.
        """

        crop_height, crop_width = (
            masked_crop.shape[:2]
        )

        if crop_height <= 0 or crop_width <= 0:
            return []

        if crop_mask is None:

            crop_mask = np.zeros(
                (crop_height, crop_width),
                dtype=np.uint8,
            )

            if (
                contour_shifted is not None
                and len(contour_shifted) >= 3
            ):

                cv2.drawContours(
                    crop_mask,
                    [contour_shifted],
                    -1,
                    255,
                    cv2.FILLED,
                )

            else:

                crop_mask[:] = 255

        target_imgsz = min(
            1024,
            max(
                640,
                max(crop_width, crop_height),
            ),
        )

        raw_candidates = []

        # Variant 1: adaptive threshold
        adaptive_image = (
            self._preprocess_adaptive_threshold(
                masked_crop,
                crop_mask,
            )
        )

        raw_candidates.extend(
            self._run_inference(
                adaptive_image,
                target_imgsz,
            )
        )

        # Variant 2: unsharp + CLAHE
        unsharp_image = (
            self._preprocess_unsharp_clahe(
                masked_crop,
                crop_mask,
            )
        )

        raw_candidates.extend(
            self._run_inference(
                unsharp_image,
                target_imgsz,
            )
        )

        # Variant 3: CLAHE
        clahe_image = (
            self._preprocess_clahe(
                masked_crop,
                crop_mask,
            )
        )

        raw_candidates.extend(
            self._run_inference(
                clahe_image,
                target_imgsz,
            )
        )

        return raw_candidates

    # ========================================================
    # MULTI-TIMBER DETECTION
    # ========================================================

    def detect(self, frame, timbers):
        """
        Detect drawings separately for each segmented timber.

        Returns a list of detection lists, matching the input
        timber order.

        timber_id is a temporary 1-based frame-local index.
        """

        if (
            frame is None
            or frame.ndim != 3
            or frame.shape[2] != 3
        ):

            raise ValueError(
                "Expected an undistorted BGR image."
            )

        height, width = frame.shape[:2]

        output = [
            [] for _ in timbers
        ]

        for index, timber in enumerate(timbers):

            contour = np.asarray(
                timber["contour"],
                dtype=np.int32,
            ).reshape(-1, 1, 2)

            if len(contour) < 3:
                continue

            x, y, w, h = cv2.boundingRect(
                contour
            )

            if w <= 0 or h <= 0:
                continue

            x0 = max(0, x)
            y0 = max(0, y)

            x1 = min(width, x + w)
            y1 = min(height, y + h)

            crop_width = x1 - x0
            crop_height = y1 - y0

            if crop_width <= 0 or crop_height <= 0:
                continue

            contour_crop = (
                contour - np.array([x0, y0])
            )

            # --------------------------------------------
            # Timber mask, including holes
            # --------------------------------------------

            if (
                "mask" in timber
                and timber["mask"] is not None
            ):

                crop_mask = timber["mask"][
                    y0:y1,
                    x0:x1,
                ].copy()

            else:

                crop_mask = np.zeros(
                    (crop_height, crop_width),
                    dtype=np.uint8,
                )

                cv2.drawContours(
                    crop_mask,
                    [contour_crop],
                    -1,
                    255,
                    cv2.FILLED,
                )

                for hole in timber.get("holes", []):

                    hole_contour = np.asarray(
                        hole,
                        dtype=np.int32,
                    ).reshape(-1, 1, 2)

                    hole_crop = (
                        hole_contour
                        - np.array([x0, y0])
                    )

                    cv2.drawContours(
                        crop_mask,
                        [hole_crop],
                        -1,
                        0,
                        cv2.FILLED,
                    )

            # --------------------------------------------
            # Erode timber mask
            # --------------------------------------------

            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (3, 3),
            )

            eroded_mask = cv2.erode(
                crop_mask,
                kernel,
            )

            # --------------------------------------------
            # Isolate timber
            # --------------------------------------------

            masked_crop = frame[
                y0:y1,
                x0:x1,
            ].copy()

            masked_crop[
                eroded_mask == 0
            ] = [180, 180, 180]

            # --------------------------------------------
            # Three-pass inference
            # --------------------------------------------

            raw_candidates = self._predict_crop(
                masked_crop,
                contour_crop,
                crop_mask=eroded_mask,
            )

            if not raw_candidates:
                continue

            boxes_list = []
            scores_list = []
            valid_candidates = []

            # --------------------------------------------
            # Candidate filtering
            # --------------------------------------------

            for candidate in raw_candidates:

                bx0, by0, bx1, by1, score, cls = (
                    candidate
                )

                bx0, bx1 = np.clip(
                    [bx0, bx1],
                    0,
                    crop_width,
                )

                by0, by1 = np.clip(
                    [by0, by1],
                    0,
                    crop_height,
                )

                if bx1 <= bx0 or by1 <= by0:
                    continue

                if self._is_edge_detection(
                    bx0,
                    by0,
                    bx1,
                    by1,
                    crop_width,
                    crop_height,
                ):
                    continue

                center_x = int(
                    np.clip(
                        (bx0 + bx1) / 2.0,
                        0,
                        crop_width - 1,
                    )
                )

                center_y = int(
                    np.clip(
                        (by0 + by1) / 2.0,
                        0,
                        crop_height - 1,
                    )
                )

                if crop_mask[
                    center_y,
                    center_x,
                ] == 0:

                    continue

                sub_mask = crop_mask[
                    int(by0):int(by1),
                    int(bx0):int(bx1),
                ]

                if (
                    sub_mask.size > 0
                    and (
                        np.count_nonzero(sub_mask)
                        / sub_mask.size
                    ) < 0.60
                ):

                    continue

                boxes_list.append([
                    bx0,
                    by0,
                    bx1 - bx0,
                    by1 - by0,
                ])

                scores_list.append(
                    score
                )

                valid_candidates.append(
                    (
                        bx0,
                        by0,
                        bx1,
                        by1,
                        score,
                        cls,
                    )
                )

            if not boxes_list:
                continue

            # --------------------------------------------
            # Non-maximum suppression
            # --------------------------------------------

            indices = cv2.dnn.NMSBoxes(
                boxes_list,
                scores_list,
                self.confidence,
                self.iou,
            )

            if len(indices) == 0:
                continue

            indices = np.asarray(
                indices
            ).flatten()

            nms_results = [
                valid_candidates[int(i)]
                for i in indices
            ]

            # --------------------------------------------
            # Merge overlapping detections
            # --------------------------------------------

            merged = (
                self._merge_overlapping_detections(
                    nms_results
                )
            )

            # --------------------------------------------
            # Build detection records
            # --------------------------------------------

            for (
                bx0,
                by0,
                bx1,
                by1,
                score,
                cls,
            ) in merged:

                gx0 = float(bx0 + x0)
                gy0 = float(by0 + y0)

                gx1 = float(bx1 + x0)
                gy1 = float(by1 + y0)

                class_name = self.class_names.get(
                    cls,
                    f"shape_{cls}",
                )

                shape_points, shape_type = (
                    generate_shape_polygon(
                        class_name,
                        [gx0, gy0, gx1, gy1],
                        image=frame,
                    )
                )

                output[index].append(
                    {
                        "class_id": cls,
                        "class_name": class_name,
                        "shape_type": shape_type,
                        "confidence": float(score),
                        "timber_id": index + 1,
                        "bbox_xyxy_px": [
                            gx0,
                            gy0,
                            gx1,
                            gy1,
                        ],
                        "center_px": [
                            (gx0 + gx1) / 2,
                            (gy0 + gy1) / 2,
                        ],
                        "shape_points_px": shape_points,
                        "dimensions_px": {
                            "width": float(gx1 - gx0),
                            "height": float(gy1 - gy0),
                        },
                        "coordinate_space": (
                            "undistorted_image"
                        ),
                    }
                )

        return output

    # ========================================================
    # OVERLAP MERGING
    # ========================================================

    @staticmethod
    def _merge_overlapping_detections(
        detections,
        containment_thresh=0.5,
    ):

        if len(detections) <= 1:
            return detections

        keep = [
            True
        ] * len(detections)

        for i in range(len(detections)):

            if not keep[i]:
                continue

            (
                bx0_i,
                by0_i,
                bx1_i,
                by1_i,
                score_i,
                cls_i,
            ) = detections[i]

            area_i = (
                (bx1_i - bx0_i)
                * (by1_i - by0_i)
            )

            if area_i <= 0:

                keep[i] = False
                continue

            for j in range(
                i + 1,
                len(detections),
            ):

                if not keep[j]:
                    continue

                (
                    bx0_j,
                    by0_j,
                    bx1_j,
                    by1_j,
                    score_j,
                    cls_j,
                ) = detections[j]

                if cls_i != cls_j:
                    continue

                area_j = (
                    (bx1_j - bx0_j)
                    * (by1_j - by0_j)
                )

                if area_j <= 0:

                    keep[j] = False
                    continue

                ix0 = max(bx0_i, bx0_j)
                iy0 = max(by0_i, by0_j)

                ix1 = min(bx1_i, bx1_j)
                iy1 = min(by1_i, by1_j)

                intersection = (
                    max(0, ix1 - ix0)
                    * max(0, iy1 - iy0)
                )

                if intersection <= 0:
                    continue

                union = (
                    area_i
                    + area_j
                    - intersection
                )

                iou = (
                    intersection / union
                    if union > 0
                    else 0
                )

                smaller_area = min(
                    area_i,
                    area_j,
                )

                containment = (
                    intersection / smaller_area
                    if smaller_area > 0
                    else 0
                )

                if (
                    iou > containment_thresh
                    or containment > containment_thresh
                ):

                    if score_i >= score_j:

                        keep[j] = False

                    else:

                        keep[i] = False
                        break

        return [
            detection
            for detection, retained in zip(
                detections,
                keep,
            )
            if retained
        ]

    # ========================================================
    # WORKSPACE FALLBACK
    # ========================================================

    def detect_workspace(
        self,
        frame,
        workspace_polygon,
    ):
        """
        Detect shapes within a workspace before individual
        timber contours are available.
        """

        if (
            frame is None
            or workspace_polygon is None
            or len(workspace_polygon) < 3
        ):

            return []

        points = np.asarray(
            workspace_polygon,
            dtype=np.int32,
        ).reshape(-1, 1, 2)

        x, y, w, h = cv2.boundingRect(
            points
        )

        height, width = frame.shape[:2]

        x0 = max(0, x)
        y0 = max(0, y)

        x1 = min(width, x + w)
        y1 = min(height, y + h)

        if x1 <= x0 or y1 <= y0:
            return []

        crop = frame[
            y0:y1,
            x0:x1,
        ].copy()

        result = self.model.predict(
            crop,
            device=self.device,
            conf=self.confidence,
            iou=self.iou,
            imgsz=self.image_size,
            agnostic_nms=True,
            verbose=False,
        )[0]

        detections = []

        if (
            result.boxes is not None
            and len(result.boxes) > 0
        ):

            rows = (
                result.boxes.data
                .detach()
                .cpu()
                .numpy()
            )

            for row in rows:

                (
                    bx0,
                    by0,
                    bx1,
                    by1,
                    score,
                    cls,
                ) = map(float, row[:6])

                cls = int(cls)

                if not np.isfinite(
                    row[:6]
                ).all():

                    continue

                gx0 = float(bx0 + x0)
                gy0 = float(by0 + y0)

                gx1 = float(bx1 + x0)
                gy1 = float(by1 + y0)

                class_name = self.class_names.get(
                    cls,
                    f"shape_{cls}",
                )

                shape_points, shape_type = (
                    generate_shape_polygon(
                        class_name,
                        [gx0, gy0, gx1, gy1],
                        image=frame,
                    )
                )

                detections.append(
                    {
                        "class_id": cls,
                        "class_name": class_name,
                        "shape_type": shape_type,
                        "confidence": float(score),
                        "timber_id": 1,
                        "bbox_xyxy_px": [
                            gx0,
                            gy0,
                            gx1,
                            gy1,
                        ],
                        "center_px": [
                            (gx0 + gx1) / 2,
                            (gy0 + gy1) / 2,
                        ],
                        "shape_points_px": shape_points,
                        "dimensions_px": {
                            "width": float(gx1 - gx0),
                            "height": float(gy1 - gy0),
                        },
                        "coordinate_space": (
                            "undistorted_image"
                        ),
                    }
                )

        return [detections]

    # ========================================================
    # METADATA
    # ========================================================

    def metadata(self):

        return {
            "model": self.model_path,
            "device": str(self.device),
            "confidence_threshold": self.confidence,
            "image_size": self.image_size,
            "iou_threshold": self.iou,
            "classes": self.class_names,
        }


# ============================================================
# VISUALIZATION
# ============================================================

def draw_detections(display, detections):
    """
    Draw detected shape polygons, centers, and labels.

    Modifies and returns the supplied display image.
    """

    for detection in detections:

        class_id = detection.get(
            "class_id",
            0,
        )

        class_name = detection.get(
            "class_name",
            "shape",
        ).lower()

        timber_id = detection.get(
            "timber_id",
            1,
        )

        confidence = detection.get(
            "confidence",
            0.0,
        )

        color = DEFAULT_COLORS.get(
            class_id,
            (0, 255, 255),
        )

        shape_points = detection.get(
            "shape_points_px",
            [],
        )

        if len(shape_points) >= 3:

            points = np.round(
                np.asarray(shape_points)
            ).astype(np.int32).reshape(-1, 1, 2)

            cv2.polylines(
                display,
                [points],
                True,
                color,
                3,
                cv2.LINE_AA,
            )

        else:

            x0, y0, x1, y1 = [
                int(round(v))
                for v in detection["bbox_xyxy_px"]
            ]

            cv2.rectangle(
                display,
                (x0, y0),
                (x1, y1),
                color,
                3,
                cv2.LINE_AA,
            )

        cx, cy = [
            int(round(v))
            for v in detection["center_px"]
        ]

        cv2.drawMarker(
            display,
            (cx, cy),
            color,
            cv2.MARKER_CROSS,
            12,
            2,
            cv2.LINE_AA,
        )

        x0 = int(round(
            detection["bbox_xyxy_px"][0]
        ))

        y0 = int(round(
            detection["bbox_xyxy_px"][1]
        ))

        label = (
            f"T{timber_id}: "
            f"{class_name.capitalize()} "
            f"{confidence:.2f}"
        )

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.60
        thickness = 2

        (text_width, text_height), baseline = (
            cv2.getTextSize(
                label,
                font,
                font_scale,
                thickness,
            )
        )

        label_y0 = max(
            0,
            y0 - text_height - 10,
        )

        cv2.rectangle(
            display,
            (x0, label_y0),
            (
                x0 + text_width + 10,
                label_y0 + text_height + 8,
            ),
            color,
            -1,
        )

        cv2.putText(
            display,
            label,
            (
                x0 + 5,
                label_y0 + text_height + 4,
            ),
            font,
            font_scale,
            (0, 0, 0),
            thickness,
            cv2.LINE_AA,
        )

    return display