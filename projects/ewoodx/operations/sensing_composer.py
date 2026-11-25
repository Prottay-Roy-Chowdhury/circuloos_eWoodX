"""
eWoodX unified sensing composer.

Independent of legacy timber segmentation operations.

Segmentation modes
------------------
single:
    Uses SingleTimberSegmenter exclusively.
    Preserves its original segmentation behavior.

multi:
    Uses MultiTimberSegmenter exclusively.
    Preserves its original segmentation behavior,
    including internal hole detection.

Both modes share downstream geometry, measurement,
streaming, runtime JSON and persistence.

The sensing entrypoint owns optional external services,
including CIRCULOOS publication.
"""

from __future__ import annotations

import copy
import json
import math
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
from collections import deque

import cv2
import numpy as np

from framework.workspace import EntityManager

from framework.sensing import (
    AngetubeCamera,
    AngetubeArucoDetector,
    AngetubeIntrinsicCalibration,
    AngetubeExtrinsicCalibration,
    ArducamCamera,
    ArducamArucoDetector,
    ArducamIntrinsicCalibration,
    ArducamExtrinsicCalibration,
)

from projects.ewoodx import config as cfg

from projects.ewoodx.operations.entity_id_allocator import (
    EWoodXEntityIdAllocator,
)

from projects.ewoodx.operations.vision.segmentation.single_timber import (
    SingleTimberSegmenter,
)

from projects.ewoodx.operations.vision.segmentation.multi_timber import (
    MultiTimberSegmenter,
)

from projects.ewoodx.operations.vision.detection.thickness_plate import (
    ThicknessPlateDetector,
)

from projects.ewoodx.operations.vision.detection.handdraw import (
    HanddrawDetector,
    draw_detections,
)

from projects.ewoodx.operations.vision.geometry.timber_geometry import (
    calculate_timber_geometry,
    calculate_parallax_parameters,
    build_timber_measurement,
)

from projects.ewoodx.operations.vision.geometry.handdraw_projection import (
    project_detections,
)

from projects.ewoodx.operations.streaming.sensing_stream_service import (
    SensingStreamService,
)

from projects.ewoodx.operations.synchronization.capture_sync_service import (
    CaptureSyncService,
    CaptureSyncError,
)


class EWoodXSensingComposer:
    """Coordinate one continuous timber sensing operation."""

    def __init__(
        self,
        entity_manager: EntityManager,
        equipment: str = "webcam",
        segmentation_mode: str = "single",
        intrinsic_file: Path | None = None,
        enable_handdraw: bool = True,
        enable_streaming: bool = True,
        enable_preview: bool = True,
        on_entity_finalized: Callable | None = None,
        enable_synchronization: bool = cfg.ENABLE_SYNCHRONIZATION,
    ) -> None:

        self.entity_manager = entity_manager

        self.equipment = equipment.strip().lower()
        self.segmentation_mode = (
            segmentation_mode.strip().lower()
        )

        if self.equipment not in ("webcam", "arducam"):
            raise ValueError(
                "Equipment must be 'webcam' or 'arducam'."
            )

        if self.segmentation_mode not in ("single", "multi"):
            raise ValueError(
                "Segmentation mode must be 'single' or 'multi'."
            )

        self.enable_preview = bool(enable_preview)
        self.on_entity_finalized = on_entity_finalized

        self.enable_synchronization = bool(
            enable_synchronization
        )

        if self.enable_synchronization and not enable_streaming:

            raise ValueError(
                "Sensing synchronization requires streaming."
            )

        self.runtime_root = Path(
            cfg.PROJECTOR_RUNTIME_ROOT
        )

        self.id_allocator = EWoodXEntityIdAllocator(
            entity_manager=entity_manager
        )

        # Equipment initialization uses the generic
        # sensing framework directly.
        self._initialize_equipment(intrinsic_file)

        # Exactly ONE segmenter is initialized.
        if self.segmentation_mode == "single":
            self.segmenter = SingleTimberSegmenter()
        else:
            self.segmenter = MultiTimberSegmenter()

        self.plate_detector = ThicknessPlateDetector()

        self.handdraw_detector = (
            HanddrawDetector()
            if enable_handdraw
            else None
        )

        self.stream_service = (
            SensingStreamService()
            if enable_streaming
            else None
        )

        self.manual_thickness_mm = float(
            cfg.TIMBER_THICKNESS_MM
        )

        self.command_queue = queue.Queue()
        self.stop_input_thread = threading.Event()

        # Capture lifecycle.
        self.active_entity_id = None
        self.active_runtime_path = None
        self.latest_valid_result = None

        # Used to retry artifact writes after
        # EntityManager has registered an entity.
        self.entity_created_for_active_id = False
        self.frozen_finalization_result = None

        self.last_finalized_entity_id = None
        self.last_error = None

        self.running = False
        self.paused = False
        self.frame_sequence = 0
        self.capture_state = "READY"

        # ---------------------------------------------------------
        # Capture synchronization
        # ---------------------------------------------------------

        self.capture_sync_service = (
            CaptureSyncService(
                camera=self.camera,
                stream_service=self.stream_service,
                should_cancel=self._should_cancel_capture,
            )
            if self.enable_synchronization
            else None
        )

        # ---------------------------------------------------------
        # Sensing performance diagnostics
        # ---------------------------------------------------------

        self.cycle_durations = deque(maxlen=10)

        self.effective_sensing_fps = 0.0

        self.last_cycle_timing = {}

    # =========================================================
    # EQUIPMENT INITIALIZATION
    # =========================================================

    def _initialize_equipment(self, intrinsic_file):

        if self.equipment == "webcam":

            self.camera = AngetubeCamera(
                camera_index=cfg.ANGETUBE_CAMERA_INDEX,
                width=cfg.ANGETUBE_IMAGE_WIDTH,
                height=cfg.ANGETUBE_IMAGE_HEIGHT,
                fps=cfg.ANGETUBE_CAMERA_FPS,
                fourcc=cfg.ANGETUBE_CAMERA_FOURCC,
                focus_mode=cfg.ANGETUBE_FOCUS_MODE,
                focus_value=cfg.ANGETUBE_FOCUS_VALUE,
                exposure_mode=cfg.ANGETUBE_EXPOSURE_MODE,
                exposure_value=cfg.ANGETUBE_EXPOSURE_VALUE,
                brightness=cfg.ANGETUBE_BRIGHTNESS,
                contrast=cfg.ANGETUBE_CONTRAST,
                saturation=cfg.ANGETUBE_SATURATION,
                sharpness=cfg.ANGETUBE_SHARPNESS,
                gain=cfg.ANGETUBE_GAIN,
                backlight_compensation=(
                    cfg.ANGETUBE_BACKLIGHT_COMPENSATION
                ),
                white_balance_mode=(
                    cfg.ANGETUBE_WHITE_BALANCE_MODE
                ),
                white_balance_temperature=(
                    cfg.ANGETUBE_WHITE_BALANCE_TEMPERATURE
                ),
                digital_zoom=cfg.ANGETUBE_DIGITAL_ZOOM,
            )

            self.aruco_detector = AngetubeArucoDetector(
                dictionary_name=(
                    cfg.ANGETUBE_ARUCO_DICTIONARY
                )
            )

            intrinsic_class = AngetubeIntrinsicCalibration
            extrinsic_class = AngetubeExtrinsicCalibration

            default_intrinsic = (
                cfg.CALIBRATION_ROOT
                / "webcam_angetube"
                / "intrinsic"
                / "camera_intrinsics.npz"
            )

            self.marker_world_positions_mm = (
                cfg.ANGETUBE_MARKER_WORLD_POSITIONS_MM
            )

            self.camera_height_mm = float(
                cfg.ANGETUBE_CAMERA_HEIGHT_MM
            )

        else:

            self.camera = ArducamCamera(
                camera_index=cfg.ARDUCAM_CAMERA_INDEX,
                width=cfg.ARDUCAM_IMAGE_WIDTH,
                height=cfg.ARDUCAM_IMAGE_HEIGHT,
            )

            self.aruco_detector = ArducamArucoDetector(
                dictionary_name=(
                    cfg.ARDUCAM_ARUCO_DICTIONARY
                )
            )

            intrinsic_class = ArducamIntrinsicCalibration
            extrinsic_class = ArducamExtrinsicCalibration

            default_intrinsic = (
                cfg.CALIBRATION_ROOT
                / "arducam"
                / "intrinsic"
                / "camera_intrinsics.npz"
            )

            self.marker_world_positions_mm = (
                cfg.ARDUCAM_MARKER_WORLD_POSITIONS_MM
            )

            self.camera_height_mm = float(
                cfg.ARDUCAM_CAMERA_HEIGHT_MM
            )

        self.intrinsic_file = Path(
            intrinsic_file
            if intrinsic_file is not None
            else default_intrinsic
        )

        if not self.intrinsic_file.is_file():
            raise FileNotFoundError(
                f"Intrinsic calibration not found: "
                f"{self.intrinsic_file}"
            )

        self.intrinsic_calibration = (
            intrinsic_class.load(self.intrinsic_file)
        )

        self.extrinsic_calibration = extrinsic_class()

    # =========================================================
    # UTILITIES
    # =========================================================

    @staticmethod
    def _timestamp():

        return datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

    @staticmethod
    def _atomic_json_write(path, data):

        path = Path(path)
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_name(
            path.name + ".tmp"
        )

        with temporary.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )

        temporary.replace(path)

    @staticmethod
    def _atomic_image_write(path, image):

        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        success, encoded = cv2.imencode(
            path.suffix,
            image,
        )

        if not success:
            raise IOError(
                f"Image encoding failed: {path}"
            )

        temporary = path.with_name(
            path.name + ".tmp"
        )

        temporary.write_bytes(
            encoded.tobytes()
        )

        temporary.replace(path)

    @staticmethod
    def _order_quad(points):

        points = np.asarray(
            points,
            dtype=np.float32,
        ).reshape(4, 2)

        center = points.mean(axis=0)

        angles = np.arctan2(
            points[:, 1] - center[1],
            points[:, 0] - center[0],
        )

        ordered = points[
            np.argsort(angles)
        ]

        first = int(
            np.argmin(
                ordered[:, 0] + ordered[:, 1]
            )
        )

        ordered = np.roll(
            ordered,
            -first,
            axis=0,
        )

        if cv2.contourArea(
            ordered.reshape(-1, 1, 2)
        ) < 0:
            ordered = ordered[::-1]

        return ordered.astype(np.float32)

    @staticmethod
    def _polygon_mask(shape, points):

        mask = np.zeros(
            shape[:2],
            dtype=np.uint8,
        )

        points = np.asarray(
            points,
            dtype=np.float32,
        ).reshape(-1, 2)

        cv2.fillPoly(
            mask,
            [
                np.round(points).astype(
                    np.int32
                )
            ],
            255,
        )

        return mask

    # =========================================================
    # LIVE CALIBRATION
    # =========================================================

    def _compute_live_homography(self, markers):

        expected_ids = set(
            self.marker_world_positions_mm.keys()
        )

        detected_ids = set(markers.keys())

        if not expected_ids.issubset(detected_ids):
            return None

        marker_centers = [
            np.asarray(
                markers[marker_id],
                dtype=np.float32,
            ).mean(axis=0)
            for marker_id in expected_ids
        ]

        workspace_centroid = np.mean(
            marker_centers,
            axis=0,
        )

        detected_outer = {}
        detected_inner = {}

        for marker_id in expected_ids:

            corners = np.asarray(
                markers[marker_id],
                dtype=np.float32,
            ).reshape(4, 2)

            distances = np.linalg.norm(
                corners - workspace_centroid,
                axis=1,
            )

            detected_inner[marker_id] = corners[
                np.argmin(distances)
            ]

            detected_outer[marker_id] = corners[
                np.argmax(distances)
            ]

        if {1, 0, 2, 3}.issubset(expected_ids):
            marker_order = [1, 0, 2, 3]
        else:
            marker_order = sorted(expected_ids)

        pixel_points = np.asarray(
            [
                detected_outer[marker_id]
                for marker_id in marker_order
            ],
            dtype=np.float32,
        )

        world_points_mm = np.asarray(
            [
                self.marker_world_positions_mm[marker_id]
                for marker_id in marker_order
            ],
            dtype=np.float32,
        )

        self.extrinsic_calibration.calibrate(
            pixel_points=pixel_points,
            world_points_mm=world_points_mm,
        )

        workspace_outer_px = self._order_quad(
            np.asarray(
                list(detected_outer.values()),
                dtype=np.float32,
            )
        )

        return {
            "outer": detected_outer,
            "inner": detected_inner,
            "markers": markers,
            "workspace_outer_px": workspace_outer_px,
            "homography": (
                self.extrinsic_calibration.homography.copy()
            ),
        }

    def _build_marker_info(self, markers, detected_outer):

        marker_info = {}

        for marker_id in self.marker_world_positions_mm:

            corners_px = np.asarray(
                markers[marker_id],
                dtype=np.float32,
            ).reshape(4, 2)

            center_px = corners_px.mean(axis=0)

            corners_mm = (
                self.extrinsic_calibration.transform_points(
                    corners_px
                )
            )

            center_mm = (
                self.extrinsic_calibration.transform_points(
                    center_px.reshape(1, 2)
                )[0]
            )

            outer_mm = (
                self.extrinsic_calibration.transform_points(
                    np.asarray(
                        detected_outer[marker_id],
                        dtype=np.float32,
                    ).reshape(1, 2)
                )[0]
            )

            marker_info[str(marker_id)] = {
                "center_mm": center_mm.tolist(),
                "corners_mm": corners_mm.tolist(),
                "outer_corner_mm": outer_mm.tolist(),
            }

        return marker_info

    # =========================================================
    # SEGMENTATION
    # =========================================================

    def _segment_timbers(
        self,
        image,
        workspace_outer_px,
        markers,
        plate,
    ):
        """
        Execute ONLY the selected segmentation algorithm.

        Return:
            detected_timbers, combined_mask

        The list wrapper is for downstream processing;
        it does not modify either segmentation algorithm.
        """

        if self.segmentation_mode == "single":

            contour, mask, corners = (
                self.segmenter.segment(
                    image=image,
                    workspace_outer_px=workspace_outer_px,
                    markers_dict=markers,
                )
            )

            if contour is None or corners is None:
                return [], mask

            # Single-timber detection has no separate
            # internal-hole output. Preserve its behavior.
            individual_mask = np.zeros(
                image.shape[:2],
                dtype=np.uint8,
            )

            cv2.drawContours(
                individual_mask,
                [contour],
                -1,
                255,
                cv2.FILLED,
            )

            detected_timbers = [
                {
                    "contour": contour,
                    "corners_px": corners,
                    "holes": [],
                    "mask": individual_mask,
                }
            ]

            return detected_timbers, mask

        # Multi mode: only MultiTimberSegmenter is called.
        return self.segmenter.segment(
            image=image,
            workspace_outer_px=workspace_outer_px,
            markers_dict=markers,
            plate_info=plate,
        )

    # =========================================================
    # COLOR
    # =========================================================

    @staticmethod
    def _sample_timber_color(image, contour, holes):

        mask = np.zeros(
            image.shape[:2],
            dtype=np.uint8,
        )

        cv2.drawContours(
            mask,
            [np.asarray(contour, dtype=np.int32)],
            -1,
            255,
            cv2.FILLED,
        )

        for hole in holes:
            cv2.drawContours(
                mask,
                [np.asarray(hole, dtype=np.int32)],
                -1,
                0,
                cv2.FILLED,
            )

        eroded = cv2.erode(
            mask,
            np.ones((7, 7), dtype=np.uint8),
        )

        if cv2.countNonZero(eroded) > 100:
            mask = eroded

        if cv2.countNonZero(mask) == 0:
            raise ValueError(
                "Empty timber color sampling mask."
            )

        lab_image = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2LAB,
        )

        rgb_image = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB,
        )

        lab = cv2.mean(
            lab_image,
            mask=mask,
        )[:3]

        rgb = cv2.mean(
            rgb_image,
            mask=mask,
        )[:3]

        r, g, b = [
            int(round(value))
            for value in rgb
        ]

        return {
            "rgb": {
                "R": r,
                "G": g,
                "B": b,
            },
            "hex": f"#{r:02X}{g:02X}{b:02X}",
            "lab": {
                "L": round(float(lab[0]), 2),
                "a": round(float(lab[1]), 2),
                "b": round(float(lab[2]), 2),
            },
        }

    
    # =========================================================
    # LIVE PREVIEW HELPERS
    # =========================================================

    @staticmethod
    def _draw_reference_overlay(
        preview,
        markers,
        workspace_outer_px=None,
        reprojection_error_mm=None,
    ):
        """Draw the reference markers and workspace boundary."""

        if workspace_outer_px is not None:
            points = np.round(
                np.asarray(workspace_outer_px)
            ).astype(np.int32).reshape(-1, 1, 2)

            if len(points) >= 3:
                cv2.polylines(
                    preview, [points], True,
                    (255, 0, 0), 2, cv2.LINE_AA,
                )

        for marker_id, corners in markers.items():
            points = np.round(
                np.asarray(corners)
            ).astype(np.int32).reshape(-1, 2)

            if len(points) != 4:
                continue

            cv2.polylines(
                preview,
                [points.reshape(-1, 1, 2)],
                True,
                (255, 255, 0),
                2,
                cv2.LINE_AA,
            )

            center = np.mean(points, axis=0).astype(int)

            cv2.putText(
                preview,
                str(marker_id),
                tuple(center),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2,
                cv2.LINE_AA,
            )

        if reprojection_error_mm is not None:
            error_text = (
                f"Homography error: "
                f"{reprojection_error_mm:.3f} mm"
            )
        elif workspace_outer_px is not None:
            error_text = "Homography error: N/A"
        else:
            error_text = "Homography: unavailable"

        cv2.putText(
            preview,
            error_text,
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    @staticmethod
    def _draw_rotated_text(
        image,
        text,
        center,
        angle_deg,
        color=(0, 255, 0),
        font_scale=0.65,
        thickness=2,
    ):
        """
        Draw text centered at a point and parallel to an edge.

        OpenCV putText does not support rotation directly.
        Render into a small transparent image and rotate it.
        """

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Keep labels upright.
        angle_deg = (angle_deg + 180.0) % 360.0 - 180.0

        if angle_deg > 90.0:
            angle_deg -= 180.0
        elif angle_deg < -90.0:
            angle_deg += 180.0

        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, font_scale, thickness,
        )

        padding = 12
        patch_w = text_w + padding * 2
        patch_h = text_h + baseline + padding * 2

        patch = np.zeros(
            (patch_h, patch_w, 4),
            dtype=np.uint8,
        )

        cv2.putText(
            patch,
            text,
            (padding, padding + text_h),
            font,
            font_scale,
            (*color, 255),
            thickness,
            cv2.LINE_AA,
        )

        rotation = cv2.getRotationMatrix2D(
            (patch_w / 2.0, patch_h / 2.0),
            -angle_deg,
            1.0,
        )

        cos_a = abs(rotation[0, 0])
        sin_a = abs(rotation[0, 1])

        rotated_w = int(
            np.ceil(patch_h * sin_a + patch_w * cos_a)
        )
        rotated_h = int(
            np.ceil(patch_h * cos_a + patch_w * sin_a)
        )

        rotation[0, 2] += rotated_w / 2.0 - patch_w / 2.0
        rotation[1, 2] += rotated_h / 2.0 - patch_h / 2.0

        rotated = cv2.warpAffine(
            patch,
            rotation,
            (rotated_w, rotated_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )

        x = int(round(center[0] - rotated_w / 2.0))
        y = int(round(center[1] - rotated_h / 2.0))

        image_h, image_w = image.shape[:2]

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(image_w, x + rotated_w)
        y2 = min(image_h, y + rotated_h)

        if x1 >= x2 or y1 >= y2:
            return

        source = rotated[
            y1 - y:y2 - y,
            x1 - x:x2 - x,
        ]

        target = image[y1:y2, x1:x2]

        alpha = (
            source[:, :, 3:4].astype(np.float32) / 255.0
        )

        target[:] = np.clip(
            target.astype(np.float32) * (1.0 - alpha)
            + source[:, :, :3].astype(np.float32) * alpha,
            0,
            255,
        ).astype(np.uint8)

    @classmethod
    def _draw_timber_dimensions(
        cls,
        preview,
        corners_px,
        measurement,
    ):
        """
        Draw oriented bounding box and dimensions.

        Length follows the longer pair of box edges.
        Width follows the shorter pair.
        """

        box = np.asarray(
            corners_px,
            dtype=np.float32,
        ).reshape(4, 2)

        cv2.polylines(
            preview,
            [np.round(box).astype(np.int32)],
            True,
            (0, 255, 0),
            3,
            cv2.LINE_AA,
        )

        edges = np.roll(box, -1, axis=0) - box
        lengths_px = np.linalg.norm(edges, axis=1)

        # Opposite edges represent the same dimension.
        pair_0 = (lengths_px[0] + lengths_px[2]) / 2.0
        pair_1 = (lengths_px[1] + lengths_px[3]) / 2.0

        if pair_0 >= pair_1:
            length_edge = 0
            width_edge = 1
        else:
            length_edge = 1
            width_edge = 0

        box_center = box.mean(axis=0)

        for edge_index, label, value in (
            (
                length_edge,
                "L",
                measurement["length_mm"],
            ),
            (
                width_edge,
                "W",
                measurement["width_mm"],
            ),
        ):
            start = box[edge_index]
            end = box[(edge_index + 1) % 4]

            direction = end - start
            edge_length = float(np.linalg.norm(direction))

            if edge_length < 1.0:
                continue

            direction /= edge_length

            midpoint = (start + end) / 2.0

            normal = np.array(
                [-direction[1], direction[0]],
                dtype=np.float32,
            )

            # Point away from the timber center.
            if np.dot(normal, midpoint - box_center) < 0:
                normal = -normal

            text_center = midpoint + normal * 26.0

            angle_deg = float(
                np.degrees(
                    np.arctan2(direction[1], direction[0])
                )
            )

            cls._draw_rotated_text(
                preview,
                f"{label}: {value:.1f} mm",
                text_center,
                angle_deg,
                color=(0, 255, 0),
            )

    def _build_preview(
        self,
        undistorted,
        markers,
        calibration,
        detected_timbers,
        measurements,
        shape_groups,
        thickness_mm,
        thickness_source,
    ):
        """Build the annotated preview for either segmentation mode."""

        preview = undistorted.copy()

        errors = (
            self.extrinsic_calibration.reprojection_errors_mm
        )

        max_error = (
            float(np.max(errors))
            if errors is not None and len(errors) > 0
            else None
        )

        self._draw_reference_overlay(
            preview,
            markers,
            workspace_outer_px=(
                calibration["workspace_outer_px"]
            ),
            reprojection_error_mm=max_error,
        )

        for index, (timber, measurement) in enumerate(
            zip(detected_timbers, measurements)
        ):
            cv2.drawContours(
                preview,
                [np.asarray(timber["contour"], dtype=np.int32)],
                -1,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

            for hole in timber.get("holes", []):
                cv2.drawContours(
                    preview,
                    [np.asarray(hole, dtype=np.int32)],
                    -1,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

            self._draw_timber_dimensions(
                preview,
                timber["corners_px"],
                measurement,
            )

            center = np.mean(
                np.asarray(
                    timber["corners_px"],
                    dtype=np.float32,
                ).reshape(-1, 2),
                axis=0,
            )

            cv2.putText(
                preview,
                f"Timber {index + 1}",
                tuple(np.round(center).astype(int)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        if self.handdraw_detector is not None:
            all_shapes = [
                shape
                for group in shape_groups
                for shape in group
            ]

            draw_detections(preview, all_shapes)

        footer = (
            f"Mode: {self.segmentation_mode.upper()} | "
            f"Timbers: {len(detected_timbers)} | "
            f"Thickness: {thickness_mm:.1f} mm "
            f"({thickness_source}) | "
            "S=Save | T=Thickness | Q=Quit"
        )

        cv2.putText(
            preview,
            footer,
            (30, preview.shape[0] - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        return preview

    # =========================================================
    # FRAME PROCESSING
    # =========================================================

    def process_frame(self, frame):
        """
        Produce a complete capture-level measurement.

        No ID allocation or persistent save occurs here.
        """

        undistorted = (
            self.intrinsic_calibration.undistort(frame)
        )

        markers = self.aruco_detector.detect(
            undistorted
        )

        calibration = self._compute_live_homography(
            markers
        )

        if calibration is None:
            return self._invalid_result(
                frame,
                undistorted,
                "Reference markers not visible",
                markers=markers,
            )

        workspace_outer_px = (
            calibration["workspace_outer_px"]
        )

        homography = calibration["homography"]

        workspace_mask = self._polygon_mask(
            undistorted.shape,
            workspace_outer_px,
        )

        plate = self.plate_detector.detect(
            image=undistorted,
            homography=homography,
            workspace_mask=workspace_mask,
        )

        detected_timbers, segmentation_mask = (
            self._segment_timbers(
                image=undistorted,
                workspace_outer_px=workspace_outer_px,
                markers=markers,
                plate=plate,
            )
        )

        if not detected_timbers:
            return self._invalid_result(
                frame,
                undistorted,
                "No valid timber detected",
                markers=markers,
                workspace_outer_px=workspace_outer_px,
            )

        if plate is not None:
            thickness_mm = float(
                plate["thickness_mm"]
            )
            thickness_source = "plate"
        else:
            thickness_mm = self.manual_thickness_mm
            thickness_source = "manual"

        camera_matrix = (
            self.intrinsic_calibration.camera_matrix
        )

        scale, origin_mm = (
            calculate_parallax_parameters(
                homography=homography,
                camera_matrix=camera_matrix,
                camera_height_mm=self.camera_height_mm,
                timber_thickness_mm=thickness_mm,
            )
        )

        # Handdraw detection follows the selected
        # segmentation results, regardless of mode.
        if self.handdraw_detector is not None:

            shape_groups = self.handdraw_detector.detect(
                undistorted,
                detected_timbers,
            )

        else:

            shape_groups = [
                [] for _ in detected_timbers
            ]

        marker_info = self._build_marker_info(
            markers,
            calibration["outer"],
        )

        errors = (
            self.extrinsic_calibration
            .reprojection_errors_mm
        )

        max_error = (
            float(np.max(errors))
            if errors is not None
            else None
        )

        measurements = []

        for index, timber in enumerate(detected_timbers):

            holes = timber.get("holes", [])

            geometry = calculate_timber_geometry(
                corners_px=timber["corners_px"],
                contour_px=timber["contour"],
                homography=homography,
                camera_matrix=camera_matrix,
                camera_height_mm=self.camera_height_mm,
                timber_thickness_mm=thickness_mm,
                holes_px=holes,
                contour_approximation_factor=(
                    cfg.TIMBER_CONTOUR_APPROX_FACTOR
                ),
            )

            color = self._sample_timber_color(
                undistorted,
                timber["contour"],
                holes,
            )

            projected_shapes = project_detections(
                detections=shape_groups[index],
                homography=homography,
                scale=scale,
                origin=origin_mm,
            )

            timber_measurement = build_timber_measurement(
                geometry=geometry,
                color=color,
                timber_thickness_mm=thickness_mm,
                thickness_source=thickness_source,
                marker_info=marker_info,
                homography_reprojection_error_mm=(
                    max_error
                ),
                hand_drawn_shapes=projected_shapes,
                timber_id=index + 1,
                source_image="image.jpg",
            )

            measurements.append(timber_measurement)

        capture_measurement = {
            "capture_id": None,
            "segmentation_mode": self.segmentation_mode,
            "timber_count": len(measurements),
            "timbers": measurements,
        }

        # -----------------------------------------------------
        # Annotated live preview
        # -----------------------------------------------------

        preview = self._build_preview(
            undistorted=undistorted,
            markers=markers,
            calibration=calibration,
            detected_timbers=detected_timbers,
            measurements=measurements,
            shape_groups=shape_groups,
            thickness_mm=thickness_mm,
            thickness_source=thickness_source,
        )

        # Preserve the selected segmenter's mask.
        # In multi mode, construct a hole-aware mask
        # from its individual detections.
        if self.segmentation_mode == "multi":

            final_mask = np.zeros(
                undistorted.shape[:2],
                dtype=np.uint8,
            )

            for timber in detected_timbers:

                final_mask = cv2.bitwise_or(
                    final_mask,
                    timber["mask"],
                )

        else:

            final_mask = segmentation_mask

        return {
            "valid": True,
            "frame": frame,
            "undistorted": undistorted,
            "preview": preview,
            "mask": final_mask,
            "measurement": capture_measurement,
        }

    def _invalid_result(
        self,
        frame,
        undistorted,
        reason,
        markers=None,
        workspace_outer_px=None,
    ):
        preview = undistorted.copy()

        self._draw_reference_overlay(
            preview,
            markers if markers is not None else {},
            workspace_outer_px=workspace_outer_px,
        )

        cv2.putText(
            preview,
            reason,
            (30, 85),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

        footer = (
            f"Mode: {self.segmentation_mode.upper()} | "
            f"Thickness: {self.manual_thickness_mm:.1f} mm "
            "(manual default) | "
            "S=Save | T=Thickness | Q=Quit"
        )

        cv2.putText(
            preview,
            footer,
            (30, preview.shape[0] - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        return {
            "valid": False,
            "reason": reason,
            "frame": frame,
            "undistorted": undistorted,
            "preview": preview,
            "mask": None,
            "measurement": None,
        }


    # =========================================================
    # ACTIVE CAPTURE
    # =========================================================

    def _ensure_active_capture(self):
        """Reserve an ID on the first valid measurement."""

        if self.active_entity_id is not None:
            return self.active_entity_id

        entity_id = self.id_allocator.allocate(
            entity_type=cfg.TIMBER_ENTITY_TYPE,
            prefix=cfg.TIMBER_ID_PREFIX,
        )

        self.active_entity_id = entity_id

        self.active_runtime_path = (
            self.runtime_root
            / f"timber_{entity_id}_measurement.json"
        )

        self.capture_state = "ACTIVE"

        print(
            f"[eWoodX] Reserved capture ID: {entity_id}"
        )

        return entity_id

    def _accept_valid_result(self, result):
        """Update the active capture and live outputs."""

        if self.capture_state == "FINALIZING":
            return

        entity_id = self._ensure_active_capture()

        snapshot = {}

        for key, value in result.items():

            snapshot[key] = (
                value.copy()
                if isinstance(value, np.ndarray)
                else copy.deepcopy(value)
            )

        measurement = snapshot["measurement"]
        measurement["capture_id"] = entity_id

        # Commit the snapshot only after its runtime
        # JSON has been written successfully.
        self._atomic_json_write(
            self.active_runtime_path,
            measurement,
        )

        self.latest_valid_result = snapshot

        if self.stream_service is not None:

            try:
                self.stream_service.publish_measurement(
                    measurement=measurement,
                    frame_id=self.frame_sequence,
                    valid=True,
                )

            except Exception as exc:
                print(
                    "[eWoodX] Measurement stream error:",
                    exc,
                )

    # =========================================================
    # FINAL ENTITY PERSISTENCE
    # =========================================================

    def finalize(self):
        """Save one persistent entity for the active capture."""

        if self.active_entity_id is None:
            raise RuntimeError(
                "No active capture to save."
            )

        if self.latest_valid_result is None:
            raise RuntimeError(
                "No valid measurement to save."
            )

        entity_id = self.active_entity_id

        if self.frozen_finalization_result is None:

            # Freeze the most recent valid snapshot.
            self.frozen_finalization_result = (
                copy.deepcopy(
                    self.latest_valid_result
                )
            )

        self.capture_state = "FINALIZING"

        snapshot = self.frozen_finalization_result

        measurement = copy.deepcopy(
            snapshot["measurement"]
        )

        measurement["capture_id"] = entity_id

        if not self.entity_created_for_active_id:

            # Capture-level metadata.
            # No first-timber dimensions are used to
            # represent an entire multi-timber capture.
            metadata = {
                "segmentation_mode": (
                    self.segmentation_mode
                ),
                "timber_count": (
                    measurement["timber_count"]
                ),
            }

            entity = self.entity_manager.create_entity(
                entity_id=entity_id,
                entity_type=cfg.TIMBER_ENTITY_TYPE,
                metadata=metadata,
            )

            self.entity_created_for_active_id = True

        else:

            entity = self.entity_manager.load_entity(
                entity_id
            )

        root = entity.root

        # If an artifact write fails, retain the frozen
        # snapshot and ID. A subsequent Save retries
        # writing to the same registered entity.
        self._atomic_image_write(
            root / "image.jpg",
            snapshot["undistorted"],
        )

        self._atomic_image_write(
            root / "mask.png",
            snapshot["mask"],
        )

        self._atomic_image_write(
            root / "overlay.jpg",
            snapshot["preview"],
        )

        self._atomic_json_write(
            root / "measurements.json",
            measurement,
        )

        finalized = {
            "entity_id": entity_id,
            "entity_path": str(root),
            "measurement_path": str(
                root / "measurements.json"
            ),
            "segmentation_mode": (
                self.segmentation_mode
            ),
            "timber_count": (
                measurement["timber_count"]
            ),
            "finalized_at": self._timestamp(),
        }

        # Local persistence has succeeded.
        self.last_finalized_entity_id = entity_id

        self.active_entity_id = None
        self.active_runtime_path = None
        self.latest_valid_result = None
        self.frozen_finalization_result = None
        self.entity_created_for_active_id = False

        self.capture_state = "READY"

        print(
            f"[eWoodX] Entity saved: {entity_id}"
        )

        # External services are coordinated by the
        # sensing entrypoint. Callback failures do not
        # invalidate local entity persistence.
        if self.on_entity_finalized is not None:

            try:
                self.on_entity_finalized(finalized)

            except Exception as exc:
                print(
                    "[eWoodX] Finalization callback error:",
                    exc,
                )

        return finalized

    # =========================================================
    # COMMANDS
    # =========================================================

    def get_status(self):

        return {
            "running": self.running,

            "paused": self.paused,

            "equipment": self.equipment,

            "segmentation_mode": self.segmentation_mode,

            "capture_state": self.capture_state,

            "active_entity_id": self.active_entity_id,

            "last_finalized_entity_id": (
                self.last_finalized_entity_id
            ),

            "has_valid_measurement": (
                self.latest_valid_result is not None
            ),

            "manual_thickness_mm": (
                self.manual_thickness_mm
            ),

            "frame_sequence": self.frame_sequence,

            "last_error": self.last_error,

            # -------------------------------------------------
            # Synchronization
            # -------------------------------------------------

            "synchronization_enabled": (
                self.enable_synchronization
            ),

            "synchronization": (
                self.capture_sync_service.get_status()
                if self.capture_sync_service is not None
                else None
            ),

            # -------------------------------------------------
            # Performance
            # -------------------------------------------------

            "effective_sensing_fps": (
                self.effective_sensing_fps
            ),

            "cycle_timing": dict(
                self.last_cycle_timing
            ),
        }

    def _execute_command(self, command, parameters=None):

        parameters = parameters or {}

        if command == "save":
            return self.finalize()

        if command == "set_thickness":

            value = float(
                parameters["thickness_mm"]
            )

            if (
                not math.isfinite(value)
                or value < 0
                or (
                    self.camera_height_mm > 0
                    and value >= self.camera_height_mm
                )
            ):
                raise ValueError(
                    "Invalid timber thickness."
                )

            self.manual_thickness_mm = value

            return {
                "thickness_mm": value
            }

        if command == "pause":
            self.paused = True
            return {"paused": True}

        if command == "resume":
            self.paused = False
            return {"paused": False}

        if command == "stop":
            self.running = False
            return {"stopping": True}

        if command == "get_status":
            return self.get_status()

        raise ValueError(
            f"Unsupported command: {command}"
        )

    def _terminal_input_loop(self):

        while not self.stop_input_thread.is_set():

            try:
                command = input(
                    "[eWoodX] S=save, T=thickness, "
                    "P=pause/resume, Q=quit: "
                ).strip().lower()

            except (EOFError, OSError):
                return

            if command == "s":

                self.command_queue.put(
                    ("save", {})
                )

            elif command == "q":

                self.command_queue.put(
                    ("stop", {})
                )

                return

            elif command == "p":

                self.command_queue.put(
                    (
                        "resume" if self.paused else "pause",
                        {},
                    )
                )

            elif command == "t":

                try:
                    value = float(
                        input("Thickness (mm): ")
                    )

                    self.command_queue.put(
                        (
                            "set_thickness",
                            {"thickness_mm": value},
                        )
                    )

                except ValueError:
                    print(
                        "[eWoodX] Invalid thickness."
                    )

    def _process_commands(self):
        """Handle local and remote commands in one place."""

        while True:

            try:
                command, parameters = (
                    self.command_queue.get_nowait()
                )

            except queue.Empty:
                break

            try:

                result = self._execute_command(
                    command,
                    parameters,
                )

                print(
                    "[eWoodX] Local command:",
                    command,
                    result,
                )

            except Exception as exc:

                self.last_error = str(exc)

                print(
                    "[eWoodX] Command error:",
                    exc,
                )

        if self.stream_service is None:
            return

        while True:

            message = (
                self.stream_service.get_sensing_command()
            )

            if message is None:
                break

            command = message.get("command")
            parameters = message.get("parameters") or {}

            try:

                result = self._execute_command(
                    command,
                    parameters,
                )

                self.stream_service.report_command_result(
                    message,
                    success=True,
                    result=result,
                )

            except Exception as exc:

                self.last_error = str(exc)

                self.stream_service.report_command_result(
                    message,
                    success=False,
                    result={
                        "error": str(exc)
                    },
                )

    # =========================================================
    # FRAME ACQUISITION
    # =========================================================

    def _should_cancel_capture(self):

        return (
            not self.running
            or self.paused
            or self.stop_input_thread.is_set()
        )


    def _capture_frame(self):

        """
        Capture one frame using the configured acquisition mode.

        Synchronization disabled:
            Direct camera acquisition.

        Synchronization enabled:
            Acquire a frame during temporary projector blanking.
        """

        if self.capture_sync_service is not None:

            return self.capture_sync_service.capture()

        return self.camera.capture()

    # =========================================================
    # SENSING PERFORMANCE
    # =========================================================

    def _update_cycle_timing(
        self,
        cycle_started_at,
        capture_duration,
        processing_duration,
    ):

        cycle_duration = (
            time.perf_counter()
            - cycle_started_at
        )

        if cycle_duration <= 0:
            return

        self.cycle_durations.append(
            cycle_duration
        )

        # Effective throughput over the latest
        # ten completed sensing cycles.
        self.effective_sensing_fps = (
            len(self.cycle_durations)
            / sum(self.cycle_durations)
        )

        timing = {
            "cycle_duration_ms": (
                cycle_duration * 1000.0
            ),

            "capture_duration_ms": (
                capture_duration * 1000.0
            ),

            "processing_duration_ms": (
                processing_duration * 1000.0
            ),

            "sync_duration_ms": 0.0,

            "sync_without_wait_ms": 0.0,

            "projection_wait_ms": 0.0,
        }

        if self.capture_sync_service is not None:

            sync_timing = (
                self.capture_sync_service.last_timing
            )

            sync_duration = sync_timing.get(
                "sync_duration_ms",
                0.0,
            )

            projection_wait = sync_timing.get(
                "projection_wait_ms",
                0.0,
            )

            timing["sync_duration_ms"] = (
                sync_duration
            )

            timing["projection_wait_ms"] = (
                projection_wait
            )

            timing["sync_without_wait_ms"] = max(
                0.0,
                sync_duration - projection_wait,
            )

        self.last_cycle_timing = timing


    def _reset_cycle_timing(self):

        self.cycle_durations.clear()

        self.effective_sensing_fps = 0.0

        self.last_cycle_timing = {}

    # =========================================================
    # MAIN LOOP
    # =========================================================

    def run(self):

        self.runtime_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        window_name = "eWoodX Sensing Composer"

        camera_open = False
        stream_started = False
        window_created = False

        try:

            self.camera.open()
            camera_open = True

            if self.enable_preview:

                cv2.namedWindow(
                    window_name,
                    cv2.WINDOW_NORMAL,
                )

                window_created = True

            if self.stream_service is not None:

                self.stream_service.start()
                stream_started = True

            self.running = True

            input_thread = threading.Thread(
                target=self._terminal_input_loop,
                daemon=True,
            )

            input_thread.start()

            print()
            print("[eWoodX] Sensing composer started.")
            print("[eWoodX] Equipment:", self.equipment)
            print(
                "[eWoodX] Segmentation mode:",
                self.segmentation_mode,
            )

            print(
                "[eWoodX] Capture synchronization:",
                "enabled"
                if self.enable_synchronization
                else "disabled",
            )

            if self.capture_sync_service is not None:

                sync_status = (
                    self.capture_sync_service.get_status()
                )

                print(
                    "[eWoodX] Sync projector:",
                    sync_status["projector_id"],
                )

                print(
                    "[eWoodX] Sync settling time:",
                    sync_status["settling_time_ms"],
                    "ms",
                )

                print(
                    "[eWoodX] Sync discard frames:",
                    sync_status["discard_frames"],
                )

                print(
                    "[eWoodX] Minimum projection visibility:",
                    sync_status["min_projection_time_ms"],
                    "ms",
                )

                print(
                    "[eWoodX] Sync command timeout:",
                    sync_status["command_timeout_ms"],
                    "ms",
                )

            self._reset_cycle_timing()

            while self.running:

                cycle_started_at = time.perf_counter()

                # -----------------------------------------------------
                # Process local and remote commands
                # -----------------------------------------------------

                self._process_commands()

                if not self.running:
                    break

                if self.paused:

                    self._reset_cycle_timing()

                    self.stop_input_thread.wait(0.03)

                    continue

                # -----------------------------------------------------
                # Frame acquisition
                # -----------------------------------------------------

                capture_started_at = time.perf_counter()

                try:

                    frame = self._capture_frame()

                except CaptureSyncError as exc:

                    self.last_error = str(exc)

                    self._reset_cycle_timing()

                    print(
                        "[eWoodX] Capture synchronization error:",
                        exc,
                    )

                    # Prevent rapid retries when the projector
                    # or stream connection is unavailable.
                    self.stop_input_thread.wait(0.1)

                    continue

                capture_duration = (
                    time.perf_counter()
                    - capture_started_at
                )

                if frame is None:

                    self._reset_cycle_timing()

                    continue

                self.frame_sequence += 1

                # -----------------------------------------------------
                # Frame processing
                # -----------------------------------------------------

                processing_started_at = time.perf_counter()

                try:

                    result = self.process_frame(frame)

                    if result["valid"]:

                        # During a failed final save,
                        # do not overwrite the frozen
                        # measurement being recovered.
                        if self.capture_state != "FINALIZING":

                            self._accept_valid_result(
                                result
                            )

                    # -------------------------------------------------
                    # Preview
                    # -------------------------------------------------

                    if self.enable_preview:

                        cv2.imshow(
                            window_name,
                            result["preview"],
                        )

                        cv2.waitKey(1)

                    # -------------------------------------------------
                    # Performance diagnostics
                    # -------------------------------------------------

                    processing_duration = (
                        time.perf_counter()
                        - processing_started_at
                    )

                    self._update_cycle_timing(
                        cycle_started_at=cycle_started_at,
                        capture_duration=capture_duration,
                        processing_duration=processing_duration,
                    )

                except Exception as exc:

                    self.last_error = str(exc)

                    self._reset_cycle_timing()

                    print(
                        "[eWoodX] Frame processing error:",
                        exc,
                    )

        finally:

            self.running = False
            self.stop_input_thread.set()

            if stream_started:
                self.stream_service.stop()

            if camera_open:
                self.camera.close()

            if window_created:
                cv2.destroyAllWindows()

            print("[eWoodX] Sensing composer stopped.")