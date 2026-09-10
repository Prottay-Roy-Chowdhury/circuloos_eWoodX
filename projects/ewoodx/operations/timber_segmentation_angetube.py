from pathlib import Path
import sys
import json

import cv2
import numpy as np


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.sensing import (
    AngetubeCamera,
    AngetubeArucoDetector,
    AngetubeExtrinsicCalibration,
    AngetubeIntrinsicCalibration,
)

from framework.workspace import (
    WorkspacePaths,
)

from projects.ewoodx.config import (
    CALIBRATION_ROOT,

    ANGETUBE_CAMERA_INDEX,
    ANGETUBE_IMAGE_WIDTH,
    ANGETUBE_IMAGE_HEIGHT,
    ANGETUBE_CAMERA_FPS,
    ANGETUBE_CAMERA_FOURCC,

    ANGETUBE_FOCUS_MODE,
    ANGETUBE_FOCUS_VALUE,
    ANGETUBE_EXPOSURE_MODE,
    ANGETUBE_EXPOSURE_VALUE,
    ANGETUBE_BRIGHTNESS,
    ANGETUBE_CONTRAST,
    ANGETUBE_SATURATION,
    ANGETUBE_SHARPNESS,
    ANGETUBE_GAIN,
    ANGETUBE_BACKLIGHT_COMPENSATION,
    ANGETUBE_WHITE_BALANCE_MODE,
    ANGETUBE_WHITE_BALANCE_TEMPERATURE,
    ANGETUBE_DIGITAL_ZOOM,

    ANGETUBE_ARUCO_DICTIONARY,
    ANGETUBE_MARKER_WORLD_POSITIONS_MM,
    ANGETUBE_CAMERA_HEIGHT_MM,

    TIMBER_THICKNESS_MM,
    TIMBER_MIN_CONTOUR_AREA_PX,
    TIMBER_CONTOUR_APPROX_FACTOR,
)


class EWoodXTimberSegmentationAngetube:
    """
    Interactive eWoodX timber sensing operation.

    The operation continuously:

    - captures Angetube frames
    - undistorts the image
    - detects the reference ArUco markers
    - calculates a fresh homography
    - segments the timber
    - calculates geometry and colour
    - displays the result live

    SPACE accepts the current processed frame and
    saves its outputs into the active workspace.

    ENTER / ESC exits the operation.
    """

    def __init__(
        self,
        workspace: WorkspacePaths,
        intrinsic_file: Path | None = None,
    ) -> None:

        self.workspace = workspace

        self.image_dir = (
            workspace.directory(
                "images"
            )
        )

        self.mask_dir = (
            workspace.directory(
                "masks"
            )
        )

        self.overlay_dir = (
            workspace.directory(
                "overlays"
            )
        )

        self.measurement_dir = (
            workspace.directory(
                "measurements"
            )
        )

        self.intrinsic_file = (
            Path(intrinsic_file)
            if intrinsic_file is not None
            else (
                CALIBRATION_ROOT
                / "webcam_angetube"
                / "intrinsic"
                / "camera_intrinsics.npz"
            )
        )

        self.marker_world_positions_mm = (
            ANGETUBE_MARKER_WORLD_POSITIONS_MM
        )

        self.camera_height_mm = (
            ANGETUBE_CAMERA_HEIGHT_MM
        )

        self.timber_thickness_mm = (
            TIMBER_THICKNESS_MM
        )

        self.min_contour_area_px = (
            TIMBER_MIN_CONTOUR_AREA_PX
        )

        self.contour_approx_factor = (
            TIMBER_CONTOUR_APPROX_FACTOR
        )

        self.camera = (
            AngetubeCamera(
                camera_index=(
                    ANGETUBE_CAMERA_INDEX
                ),
                width=(
                    ANGETUBE_IMAGE_WIDTH
                ),
                height=(
                    ANGETUBE_IMAGE_HEIGHT
                ),
                fps=(
                    ANGETUBE_CAMERA_FPS
                ),
                fourcc=(
                    ANGETUBE_CAMERA_FOURCC
                ),
                focus_mode=(
                    ANGETUBE_FOCUS_MODE
                ),
                focus_value=(
                    ANGETUBE_FOCUS_VALUE
                ),
                exposure_mode=(
                    ANGETUBE_EXPOSURE_MODE
                ),
                exposure_value=(
                    ANGETUBE_EXPOSURE_VALUE
                ),
                brightness=(
                    ANGETUBE_BRIGHTNESS
                ),
                contrast=(
                    ANGETUBE_CONTRAST
                ),
                saturation=(
                    ANGETUBE_SATURATION
                ),
                sharpness=(
                    ANGETUBE_SHARPNESS
                ),
                gain=(
                    ANGETUBE_GAIN
                ),
                backlight_compensation=(
                    ANGETUBE_BACKLIGHT_COMPENSATION
                ),
                white_balance_mode=(
                    ANGETUBE_WHITE_BALANCE_MODE
                ),
                white_balance_temperature=(
                    ANGETUBE_WHITE_BALANCE_TEMPERATURE
                ),
                digital_zoom=(
                    ANGETUBE_DIGITAL_ZOOM
                ),
            )
        )

        self.detector = (
            AngetubeArucoDetector(
                dictionary_name=(
                    ANGETUBE_ARUCO_DICTIONARY
                )
            )
        )

        self.intrinsic_calibration = (
            self._load_intrinsic_calibration()
        )

        # This object is intentionally recalibrated
        # for every live frame.
        self.extrinsic_calibration = (
            AngetubeExtrinsicCalibration()
        )

        self.capture_index = (
            self._find_next_capture_index()
        )

    # -----------------------------------------------------------------
    # Main operation
    # -----------------------------------------------------------------

    def run(
        self,
    ) -> None:
        """
        Start continuous live timber sensing.

        SPACE = save current valid result
        T = change timber thickness
        ENTER / ESC = exit
        """

        print(
            "[eWoodX] Timber segmentation"
        )

        print(
            "[eWoodX] Workspace:"
        )

        print(
            self.workspace.root
        )

        print(
            "[eWoodX] Opening camera..."
        )

        self.camera.open()

        print(
            "[eWoodX] Camera resolution:"
        )

        print(
            self.camera.resolution
        )

        print(
            "[eWoodX] SPACE = save current timber"
        )

        print(
            "[eWoodX] T = change timber thickness"
        )

        print(
            "[eWoodX] Current timber thickness:"
        )

        print(
            f"{self.timber_thickness_mm:.1f} mm"
        )

        print(
            "[eWoodX] ENTER / ESC = exit"
        )

        try:

            while True:

                frame = (
                    self.camera.capture()
                )

                result = (
                    self.process_frame(
                        frame
                    )
                )

                cv2.imshow(
                    "eWoodX Timber Segmentation",
                    result["preview"],
                )

                key = (
                    cv2.waitKey(1)
                    & 0xFF
                )

                if key in (
                    ord("t"),
                    ord("T"),
                ):

                    print()

                    print(
                        "[eWoodX] Current timber thickness:"
                    )

                    print(
                        f"{self.timber_thickness_mm:.1f} mm"
                    )

                    try:

                        value = (
                            input(
                                "Enter timber thickness in mm: "
                            )
                            .strip()
                        )

                        new_thickness = float(
                            value
                        )

                        if new_thickness < 0:

                            print(
                                "[eWoodX] Timber thickness "
                                "cannot be negative."
                            )

                            continue

                        if (
                            new_thickness
                            >= self.camera_height_mm
                        ):

                            print(
                                "[eWoodX] Timber thickness "
                                "must be smaller than "
                                "the camera height."
                            )

                            continue

                        self.timber_thickness_mm = (
                            new_thickness
                        )

                        print(
                            "[eWoodX] Timber thickness set to:"
                        )

                        print(
                            f"{self.timber_thickness_mm:.1f} mm"
                        )

                    except (ValueError, EOFError):

                        print(
                            "[eWoodX] Invalid thickness. "
                            "Value unchanged."
                        )

                elif key == 32:

                    if not result["valid"]:

                        print(
                            "[eWoodX] Current frame "
                            "is not valid. Nothing saved."
                        )

                        continue

                    self._save_outputs(
                        result
                    )

                elif key in (
                    10,
                    13,
                    27,
                ):

                    print(
                        "[eWoodX] Sensing stopped."
                    )

                    break

        finally:

            self.camera.close()

            cv2.destroyAllWindows()

    # -----------------------------------------------------------------
    # Per-frame processing
    # -----------------------------------------------------------------

    def process_frame(
        self,
        frame: np.ndarray,
    ) -> dict:

        undistorted = (
            self.intrinsic_calibration
            .undistort(
                frame
            )
        )

        detected_markers = (
            self.detector.detect(
                undistorted
            )
        )

        live_calibration = (
            self._compute_live_homography(
                detected_markers
            )
        )

        if live_calibration is None:

            preview = (
                self._build_invalid_preview(
                    undistorted,
                    detected_markers,
                    "Reference markers not visible",
                )
            )

            return {
                "valid": False,
                "frame": frame,
                "undistorted": undistorted,
                "preview": preview,
                "mask": None,
                "measurement": None,
            }

        (
            detected_outer,
            detected_inner,
            detected_all,
        ) = live_calibration

        workspace_outer_px = (
            self._order_quad(
                np.asarray(
                    list(
                        detected_outer.values()
                    ),
                    dtype=np.float32,
                )
            )
        )

        (
            contour,
            timber_mask,
            timber_corners_px,
        ) = self._segment_timber(
            undistorted,
            workspace_outer_px,
            detected_all,
        )

        if (
            contour is None
            or timber_corners_px is None
        ):

            preview = (
                self._build_invalid_preview(
                    undistorted,
                    detected_markers,
                    "No valid timber detected",
                    workspace_outer_px=(
                        workspace_outer_px
                    ),
                )
            )

            return {
                "valid": False,
                "frame": frame,
                "undistorted": undistorted,
                "preview": preview,
                "mask": timber_mask,
                "measurement": None,
            }

        timber_corners_mm = (
            self._transform_points_to_mm(
                timber_corners_px
            )
        )

        timber_corners_mm = (
            self._apply_parallax_compensation(
                timber_corners_mm
            )
        )

        perimeter = (
            cv2.arcLength(
                contour,
                True,
            )
        )

        epsilon = (
            self.contour_approx_factor
            * perimeter
        )

        contour_approx = (
            cv2.approxPolyDP(
                contour,
                epsilon,
                True,
            )
        )

        contour_px = (
            contour_approx
            .reshape(
                -1,
                2,
            )
            .astype(
                np.float32
            )
        )

        contour_mm = (
            self._transform_points_to_mm(
                contour_px
            )
        )

        contour_mm = (
            self._apply_parallax_compensation(
                contour_mm
            )
        )

        geometry = (
            self._calculate_geometry(
                timber_corners_mm,
                contour_mm,
            )
        )

        color = (
            self._sample_timber_color(
                undistorted,
                contour,
            )
        )

        marker_info = (
            self._build_marker_info(
                detected_all,
                detected_outer,
            )
        )

        measurement = (
            self._build_result(
                geometry=geometry,
                timber_corners_mm=(
                    timber_corners_mm
                ),
                contour_mm=(
                    contour_mm
                ),
                color=color,
                marker_info=(
                    marker_info
                ),
            )
        )

        preview = (
            self._build_preview(
                undistorted,
                contour,
                timber_corners_px,
                workspace_outer_px,
                detected_all,
                measurement,
            )
        )

        return {
            "valid": True,
            "frame": frame,
            "undistorted": undistorted,
            "preview": preview,
            "mask": timber_mask,
            "measurement": measurement,
        }

    # -----------------------------------------------------------------
    # Intrinsic calibration
    # -----------------------------------------------------------------

    def _load_intrinsic_calibration(
        self,
    ) -> AngetubeIntrinsicCalibration:

        if not self.intrinsic_file.exists():

            raise FileNotFoundError(
                "Angetube intrinsic calibration "
                "file not found: "
                f"{self.intrinsic_file}"
            )

        return (
            AngetubeIntrinsicCalibration.load(
                self.intrinsic_file
            )
        )

    # -----------------------------------------------------------------
    # Live homography
    # -----------------------------------------------------------------

    def _compute_live_homography(
        self,
        detected_markers: dict,
    ):

        expected_ids = set(
            self.marker_world_positions_mm.keys()
        )

        detected_ids = set(
            detected_markers.keys()
        )

        if not expected_ids.issubset(
            detected_ids
        ):
            return None

        marker_centers = [
            np.asarray(
                detected_markers[
                    marker_id
                ],
                dtype=np.float32,
            ).mean(
                axis=0
            )
            for marker_id
            in expected_ids
        ]

        workspace_centroid = (
            np.mean(
                marker_centers,
                axis=0,
            )
        )

        detected_outer = {}
        detected_inner = {}

        for marker_id in expected_ids:

            marker_corners = np.asarray(
                detected_markers[
                    marker_id
                ],
                dtype=np.float32,
            )

            distances = (
                np.linalg.norm(
                    marker_corners
                    - workspace_centroid,
                    axis=1,
                )
            )

            detected_inner[
                marker_id
            ] = (
                marker_corners[
                    np.argmin(
                        distances
                    )
                ]
            )

            detected_outer[
                marker_id
            ] = (
                marker_corners[
                    np.argmax(
                        distances
                    )
                ]
            )

        if {
            1,
            0,
            2,
            3,
        }.issubset(
            expected_ids
        ):

            marker_order = [
                1,
                0,
                2,
                3,
            ]

        else:

            marker_order = sorted(
                expected_ids
            )

        pixel_points = np.asarray(
            [
                detected_outer[
                    marker_id
                ]
                for marker_id
                in marker_order
            ],
            dtype=np.float32,
        )

        world_points_mm = np.asarray(
            [
                self.marker_world_positions_mm[
                    marker_id
                ]
                for marker_id
                in marker_order
            ],
            dtype=np.float32,
        )

        # Generic framework homography.
        # Recomputed for EVERY current frame.
        self.extrinsic_calibration.calibrate(
            pixel_points=(
                pixel_points
            ),
            world_points_mm=(
                world_points_mm
            ),
        )

        return (
            detected_outer,
            detected_inner,
            detected_markers,
        )

    # -----------------------------------------------------------------
    # Timber segmentation
    # -----------------------------------------------------------------

    def _segment_timber(
        self,
        image: np.ndarray,
        workspace_outer_px: np.ndarray,
        markers_dict: dict,
    ):

        workspace_mask = (
            self._polygon_mask(
                image.shape,
                workspace_outer_px,
            )
        )

        markers_mask = np.zeros(
            image.shape[:2],
            dtype=np.uint8,
        )

        for marker_corners in (
            markers_dict.values()
        ):

            points = (
                np.round(
                    marker_corners
                )
                .astype(
                    np.int32
                )
            )

            cv2.fillPoly(
                markers_mask,
                [points],
                255,
            )

        marker_kernel = (
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (
                    15,
                    15,
                ),
            )
        )

        markers_mask = (
            cv2.dilate(
                markers_mask,
                marker_kernel,
            )
        )

        usable_roi = (
            cv2.bitwise_and(
                workspace_mask,
                cv2.bitwise_not(
                    markers_mask
                ),
            )
        )

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        gray_blur = (
            cv2.GaussianBlur(
                gray,
                (
                    5,
                    5,
                ),
                0,
            )
        )

        roi_pixels = (
            gray_blur[
                usable_roi > 0
            ]
        )

        if roi_pixels.size < 100:

            return (
                None,
                np.zeros_like(
                    gray
                ),
                None,
            )

        otsu_threshold, _ = (
            cv2.threshold(
                roi_pixels.reshape(
                    -1,
                    1,
                ),
                0,
                255,
                (
                    cv2.THRESH_BINARY
                    + cv2.THRESH_OTSU
                ),
            )
        )

        black_threshold = int(
            np.clip(
                otsu_threshold,
                35,
                120,
            )
        )

        dark_mask = np.zeros_like(
            gray
        )

        dark_mask[
            (
                gray_blur
                <= black_threshold
            )
            & (
                usable_roi
                > 0
            )
        ] = 255

        background_kernel = (
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (
                    15,
                    15,
                ),
            )
        )

        dark_mask_closed = (
            cv2.morphologyEx(
                dark_mask,
                cv2.MORPH_CLOSE,
                background_kernel,
            )
        )

        curtain_contours, _ = (
            cv2.findContours(
                dark_mask_closed,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
        )

        curtain_domain = (
            np.zeros_like(
                gray
            )
        )

        for curtain_contour in (
            curtain_contours
        ):

            if (
                cv2.contourArea(
                    curtain_contour
                )
                > 15000
            ):

                hull = cv2.convexHull(
                    curtain_contour
                )

                cv2.drawContours(
                    curtain_domain,
                    [hull],
                    -1,
                    255,
                    thickness=(
                        cv2.FILLED
                    ),
                )

        usable_area = (
            cv2.countNonZero(
                usable_roi
            )
        )

        curtain_area = (
            cv2.countNonZero(
                curtain_domain
            )
        )

        if (
            usable_area > 0
            and curtain_area
            < 0.25 * usable_area
        ):

            curtain_domain = (
                usable_roi.copy()
            )

        timber_raw = (
            cv2.bitwise_and(
                curtain_domain,
                cv2.bitwise_not(
                    dark_mask_closed
                ),
            )
        )

        timber_raw = (
            cv2.bitwise_and(
                timber_raw,
                usable_roi,
            )
        )

        close_kernel = (
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (
                    15,
                    15,
                ),
            )
        )

        timber_mask = (
            cv2.morphologyEx(
                timber_raw,
                cv2.MORPH_CLOSE,
                close_kernel,
            )
        )

        open_kernel = (
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (
                    7,
                    7,
                ),
            )
        )

        timber_mask = (
            cv2.morphologyEx(
                timber_mask,
                cv2.MORPH_OPEN,
                open_kernel,
            )
        )

        contours, _ = (
            cv2.findContours(
                timber_mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
        )

        candidates = []

        for contour in contours:

            area = (
                cv2.contourArea(
                    contour
                )
            )

            if (
                area
                < self.min_contour_area_px
            ):
                continue

            hull = cv2.convexHull(
                contour
            )

            hull_area = (
                cv2.contourArea(
                    hull
                )
            )

            if hull_area <= 0:
                continue

            solidity = (
                area
                / hull_area
            )

            if solidity < 0.70:
                continue

            rect = (
                cv2.minAreaRect(
                    contour
                )
            )

            rect_width, rect_height = (
                rect[1]
            )

            aspect_ratio = (
                max(
                    rect_width,
                    rect_height,
                )
                / max(
                    min(
                        rect_width,
                        rect_height,
                    ),
                    1.0,
                )
            )

            if aspect_ratio < 1.8:
                continue

            score = (
                area
                * min(
                    aspect_ratio
                    / 4.0,
                    2.0,
                )
                * solidity
            )

            candidates.append(
                (
                    score,
                    contour,
                )
            )

        if not candidates:

            return (
                None,
                timber_mask,
                None,
            )

        candidates.sort(
            key=lambda item: (
                item[0]
            ),
            reverse=True,
        )

        best_contour = (
            candidates[0][1]
        )

        timber_corners_px = (
            self._get_contour_oriented_box(
                best_contour
            )
        )

        return (
            best_contour,
            timber_mask,
            timber_corners_px,
        )

    # -----------------------------------------------------------------
    # Geometry helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _polygon_mask(
        shape,
        points,
    ):

        mask = np.zeros(
            shape[:2],
            dtype=np.uint8,
        )

        points = (
            np.asarray(
                points,
                dtype=np.float32,
            )
        )

        points = (
            np.round(
                points
            )
            .astype(
                np.int32
            )
        )

        cv2.fillPoly(
            mask,
            [points],
            255,
        )

        return mask

    @staticmethod
    def _order_quad(
        points,
    ):

        points = (
            np.asarray(
                points,
                dtype=np.float32,
            )
            .reshape(
                4,
                2,
            )
        )

        center = (
            points.mean(
                axis=0
            )
        )

        angles = (
            np.arctan2(
                points[:, 1]
                - center[1],
                points[:, 0]
                - center[0],
            )
        )

        order = (
            np.argsort(
                angles
            )
        )

        ordered = (
            points[
                order
            ]
        )

        sums = (
            ordered[:, 0]
            + ordered[:, 1]
        )

        first = int(
            np.argmin(
                sums
            )
        )

        ordered = (
            np.roll(
                ordered,
                -first,
                axis=0,
            )
        )

        area = (
            cv2.contourArea(
                ordered.reshape(
                    -1,
                    1,
                    2,
                )
            )
        )

        if area < 0:
            ordered = (
                ordered[::-1]
            )

        return (
            ordered.astype(
                np.float32
            )
        )

    def _get_contour_oriented_box(
        self,
        contour,
    ):

        rect = (
            cv2.minAreaRect(
                contour
            )
        )

        box = (
            cv2.boxPoints(
                rect
            )
        )

        return (
            self._order_quad(
                box
            )
        )

    # -----------------------------------------------------------------
    # Pixel -> mm
    # -----------------------------------------------------------------

    def _transform_points_to_mm(
        self,
        pixel_points,
    ):

        return (
            self.extrinsic_calibration
            .transform_points(
                np.asarray(
                    pixel_points,
                    dtype=np.float32,
                )
            )
        )

    def _apply_parallax_compensation(
        self,
        points_mm,
    ):

        points_mm = np.asarray(
            points_mm,
            dtype=np.float32,
        )

        if (
            self.timber_thickness_mm
            <= 0
        ):

            return points_mm

        if self.camera_height_mm <= 0:

            return points_mm

        if (
            self.timber_thickness_mm
            >= self.camera_height_mm
        ):

            return points_mm

        camera_matrix = (
            self.intrinsic_calibration
            .camera_matrix
        )

        cx = float(
            camera_matrix[
                0,
                2,
            ]
        )

        cy = float(
            camera_matrix[
                1,
                2,
            ]
        )

        optical_center_mm = (
            self._transform_points_to_mm(
                np.asarray(
                    [
                        [
                            cx,
                            cy,
                        ]
                    ],
                    dtype=np.float32,
                )
            )[0]
        )

        scale_factor = (
            (
                self.camera_height_mm
                - self.timber_thickness_mm
            )
            / self.camera_height_mm
        )

        corrected = (
            optical_center_mm
            + (
                points_mm
                - optical_center_mm
            )
            * scale_factor
        )

        return (
            corrected.astype(
                np.float32
            )
        )

    # -----------------------------------------------------------------
    # Timber measurement
    # -----------------------------------------------------------------

    @staticmethod
    def _calculate_geometry(
        timber_corners_mm,
        contour_mm,
    ):

        timber_corners_mm = (
            np.asarray(
                timber_corners_mm,
                dtype=np.float32,
            )
            .reshape(
                4,
                2,
            )
        )

        side_lengths = []

        for index in range(4):

            next_index = (
                (index + 1)
                % 4
            )

            length = float(
                np.linalg.norm(
                    timber_corners_mm[
                        next_index
                    ]
                    - timber_corners_mm[
                        index
                    ]
                )
            )

            side_lengths.append(
                length
            )

        dimension_a = (
            (
                side_lengths[0]
                + side_lengths[2]
            )
            / 2.0
        )

        dimension_b = (
            (
                side_lengths[1]
                + side_lengths[3]
            )
            / 2.0
        )

        length_mm = max(
            dimension_a,
            dimension_b,
        )

        width_mm = min(
            dimension_a,
            dimension_b,
        )

        contour_for_area = (
            np.asarray(
                contour_mm,
                dtype=np.float32,
            )
            .reshape(
                -1,
                1,
                2,
            )
        )

        surface_area_mm2 = abs(
            float(
                cv2.contourArea(
                    contour_for_area
                )
            )
        )

        return {
            "length_mm": (
                length_mm
            ),
            "width_mm": (
                width_mm
            ),
            "side_lengths_mm": (
                side_lengths
            ),
            "surface_area_mm2": (
                surface_area_mm2
            ),
            "surface_area_cm2": (
                surface_area_mm2
                / 100.0
            ),
        }

    # -----------------------------------------------------------------
    # Colour
    # -----------------------------------------------------------------

    @staticmethod
    def _sample_timber_color(
        image_bgr,
        contour,
    ):

        mask = np.zeros(
            image_bgr.shape[:2],
            dtype=np.uint8,
        )

        cv2.drawContours(
            mask,
            [contour],
            -1,
            255,
            thickness=cv2.FILLED,
        )

        if (
            cv2.countNonZero(
                mask
            )
            > 400
        ):

            eroded = (
                cv2.erode(
                    mask,
                    np.ones(
                        (
                            7,
                            7,
                        ),
                        dtype=np.uint8,
                    ),
                )
            )

            if (
                cv2.countNonZero(
                    eroded
                )
                > 100
            ):

                mask = eroded

        lab_image = (
            cv2.cvtColor(
                image_bgr,
                cv2.COLOR_BGR2LAB,
            )
        )

        mean_lab = (
            cv2.mean(
                lab_image,
                mask=mask,
            )[:3]
        )

        rgb_image = (
            cv2.cvtColor(
                image_bgr,
                cv2.COLOR_BGR2RGB,
            )
        )

        mean_rgb = (
            cv2.mean(
                rgb_image,
                mask=mask,
            )[:3]
        )

        red = int(
            round(
                mean_rgb[0]
            )
        )

        green = int(
            round(
                mean_rgb[1]
            )
        )

        blue = int(
            round(
                mean_rgb[2]
            )
        )

        return {
            "lab": {
                "L": round(
                    float(
                        mean_lab[0]
                    ),
                    2,
                ),
                "a": round(
                    float(
                        mean_lab[1]
                    ),
                    2,
                ),
                "b": round(
                    float(
                        mean_lab[2]
                    ),
                    2,
                ),
            },
            "rgb": {
                "R": red,
                "G": green,
                "B": blue,
            },
            "hex": (
                f"#{red:02X}"
                f"{green:02X}"
                f"{blue:02X}"
            ),
        }

    # -----------------------------------------------------------------
    # Marker information
    # -----------------------------------------------------------------

    def _build_marker_info(
        self,
        detected_all,
        detected_outer,
    ):

        marker_info = {}

        for marker_id in (
            self.marker_world_positions_mm
        ):

            corners_px = np.asarray(
                detected_all[
                    marker_id
                ],
                dtype=np.float32,
            )

            center_px = (
                corners_px.mean(
                    axis=0
                )
            )

            corners_mm = (
                self._transform_points_to_mm(
                    corners_px
                )
            )

            center_mm = (
                self._transform_points_to_mm(
                    np.asarray(
                        [
                            center_px
                        ],
                        dtype=np.float32,
                    )
                )[0]
            )

            outer_mm = (
                self._transform_points_to_mm(
                    np.asarray(
                        [
                            detected_outer[
                                marker_id
                            ]
                        ],
                        dtype=np.float32,
                    )
                )[0]
            )

            marker_info[
                str(
                    marker_id
                )
            ] = {
                "center_mm": (
                    center_mm
                    .tolist()
                ),
                "corners_mm": (
                    corners_mm
                    .tolist()
                ),
                "outer_corner_mm": (
                    outer_mm
                    .tolist()
                ),
            }

        return marker_info

    # -----------------------------------------------------------------
    # Result
    # -----------------------------------------------------------------

    def _build_result(
        self,
        geometry,
        timber_corners_mm,
        contour_mm,
        color,
        marker_info,
    ):

        errors = (
            self.extrinsic_calibration
            .reprojection_errors_mm
        )

        max_error = (
            float(
                np.max(
                    errors
                )
            )
            if errors is not None
            else None
        )

        return {
            "timber_id": None,
            "source_image": None,
            "reference_frame": {
                "origin_marker_id": 1,
                "origin_mm": [
                    0.0,
                    0.0,
                    0.0,
                ],
                "x_axis": [
                    1.0,
                    0.0,
                    0.0,
                ],
                "y_axis": [
                    0.0,
                    1.0,
                    0.0,
                ],
                "z_axis": [
                    0.0,
                    0.0,
                    1.0,
                ],
                "description": (
                    "Origin at Marker 1 outer "
                    "corner; +X towards Marker 0; "
                    "+Y towards Marker 2."
                ),
            },
            "markers_world_mm": (
                marker_info
            ),
            "homography_reprojection_error_mm": (
                max_error
            ),
            "length_mm": round(
                geometry[
                    "length_mm"
                ],
                2,
            ),
            "width_mm": round(
                geometry[
                    "width_mm"
                ],
                2,
            ),
            "surface_area_mm2": round(
                geometry[
                    "surface_area_mm2"
                ],
                2,
            ),
            "surface_area_cm2": round(
                geometry[
                    "surface_area_cm2"
                ],
                2,
            ),
            "side_lengths_mm": [
                round(
                    value,
                    2,
                )
                for value in (
                    geometry[
                        "side_lengths_mm"
                    ]
                )
            ],
            "corners_mm": (
                np.asarray(
                    timber_corners_mm
                )
                .round(
                    3
                )
                .tolist()
            ),
            "contour_mm": (
                np.asarray(
                    contour_mm
                )
                .round(
                    3
                )
                .tolist()
            ),
            "timber_thickness_mm": (
                self.timber_thickness_mm
            ),
            "color_rgb": (
                color[
                    "rgb"
                ]
            ),
            "color_hex": (
                color[
                    "hex"
                ]
            ),
            "color_lab": (
                color[
                    "lab"
                ]
            ),
            "defects": [],
        }

    # -----------------------------------------------------------------
    # Live preview
    # -----------------------------------------------------------------

    def _build_preview(
        self,
        image,
        contour,
        timber_corners_px,
        workspace_outer_px,
        detected_markers,
        measurement,
    ):

        preview = image.copy()

        workspace_points = (
            np.round(
                workspace_outer_px
            )
            .astype(
                np.int32
            )
        )

        cv2.polylines(
            preview,
            [
                workspace_points
            ],
            True,
            (
                255,
                0,
                0,
            ),
            2,
        )

        for marker_id, corners in (
            detected_markers.items()
        ):

            corners_int = (
                np.round(
                    corners
                )
                .astype(
                    np.int32
                )
            )

            cv2.polylines(
                preview,
                [
                    corners_int
                ],
                True,
                (
                    255,
                    255,
                    0,
                ),
                2,
            )

            center = (
                corners_int.mean(
                    axis=0
                )
                .astype(
                    int
                )
            )

            cv2.putText(
                preview,
                str(
                    marker_id
                ),
                tuple(
                    center
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (
                    255,
                    255,
                    0,
                ),
                2,
            )

        cv2.drawContours(
            preview,
            [
                contour
            ],
            -1,
            (
                0,
                255,
                255,
            ),
            2,
        )

        box = (
            np.round(
                timber_corners_px
            )
            .astype(
                np.int32
            )
        )

        cv2.polylines(
            preview,
            [
                box
            ],
            True,
            (
                0,
                255,
                0,
            ),
            3,
        )

        length_text = (
            f"Length: "
            f"{measurement['length_mm']:.1f} mm"
        )

        width_text = (
            f"Width: "
            f"{measurement['width_mm']:.1f} mm"
        )

        error = (
            measurement[
                "homography_reprojection_error_mm"
            ]
        )

        if error is None:

            error_text = (
                "Homography error: N/A"
            )

        else:

            error_text = (
                "Homography error: "
                f"{error:.3f} mm"
            )

        cv2.putText(
            preview,
            length_text,
            (
                30,
                40,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (
                0,
                255,
                0,
            ),
            2,
        )

        cv2.putText(
            preview,
            width_text,
            (
                30,
                75,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (
                0,
                255,
                0,
            ),
            2,
        )

        cv2.putText(
            preview,
            error_text,
            (
                30,
                110,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (
                255,
                255,
                255,
            ),
            2,
        )

        cv2.putText(
            preview,
            (
                "SPACE = save | "
                f"T = thickness ({self.timber_thickness_mm:.1f} mm) | "
                "ENTER/ESC = exit"
            ),
            (
                30,
                preview.shape[0] - 30,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (
                255,
                255,
                255,
            ),
            2,
        )

        return preview

    def _build_invalid_preview(
        self,
        image,
        detected_markers,
        message,
        workspace_outer_px=None,
    ):

        preview = image.copy()

        if workspace_outer_px is not None:

            points = (
                np.round(
                    workspace_outer_px
                )
                .astype(
                    np.int32
                )
            )

            cv2.polylines(
                preview,
                [
                    points
                ],
                True,
                (
                    255,
                    0,
                    0,
                ),
                2,
            )

        for marker_id, corners in (
            detected_markers.items()
        ):

            points = (
                np.round(
                    corners
                )
                .astype(
                    np.int32
                )
            )

            cv2.polylines(
                preview,
                [
                    points
                ],
                True,
                (
                    255,
                    255,
                    0,
                ),
                2,
            )

            center = (
                points.mean(
                    axis=0
                )
                .astype(
                    int
                )
            )

            cv2.putText(
                preview,
                str(
                    marker_id
                ),
                tuple(
                    center
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (
                    255,
                    255,
                    0,
                ),
                2,
            )

        cv2.putText(
            preview,
            message,
            (
                30,
                40,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (
                0,
                0,
                255,
            ),
            2,
        )

        cv2.putText(
            preview,
            (
                "SPACE = save | "
                f"T = thickness ({self.timber_thickness_mm:.1f} mm) | "
                "ENTER/ESC = exit"
            ),
            (
                30,
                preview.shape[0] - 30,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (
                255,
                255,
                255,
            ),
            2,
        )

        return preview

    # -----------------------------------------------------------------
    # Saving
    # -----------------------------------------------------------------

    def _save_outputs(
        self,
        result,
    ) -> None:

        timber_id = (
            f"timber_"
            f"{self.capture_index:04d}"
        )

        image_file = (
            self.image_dir
            / f"{timber_id}.jpg"
        )

        mask_file = (
            self.mask_dir
            / f"{timber_id}_mask.png"
        )

        overlay_file = (
            self.overlay_dir
            / f"{timber_id}_overlay.jpg"
        )

        measurement_file = (
            self.measurement_dir
            / f"{timber_id}.json"
        )

        image_success = (
            cv2.imwrite(
                str(
                    image_file
                ),
                result[
                    "frame"
                ],
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    100,
                ],
            )
        )

        if not image_success:

            raise RuntimeError(
                "Could not save image: "
                f"{image_file}"
            )

        if result["mask"] is not None:

            mask_success = (
                cv2.imwrite(
                    str(
                        mask_file
                    ),
                    result[
                        "mask"
                    ],
                )
            )

            if not mask_success:

                raise RuntimeError(
                    "Could not save mask: "
                    f"{mask_file}"
                )

        overlay_success = (
            cv2.imwrite(
                str(
                    overlay_file
                ),
                result[
                    "preview"
                ],
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    100,
                ],
            )
        )

        if not overlay_success:

            raise RuntimeError(
                "Could not save overlay: "
                f"{overlay_file}"
            )

        measurement = dict(
            result[
                "measurement"
            ]
        )

        measurement[
            "timber_id"
        ] = timber_id

        measurement[
            "source_image"
        ] = image_file.name

        measurement_file.write_text(
            json.dumps(
                measurement,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            "[eWoodX] Timber saved:"
        )

        print(
            f"  ID: {timber_id}"
        )

        print(
            f"  Image: {image_file}"
        )

        print(
            f"  Mask: {mask_file}"
        )

        print(
            f"  Overlay: {overlay_file}"
        )

        print(
            f"  Measurement: {measurement_file}"
        )

        self.capture_index += 1

    def _find_next_capture_index(
        self,
    ) -> int:

        highest_index = 0

        for file_path in (
            self.measurement_dir.glob(
                "timber_*.json"
            )
        ):

            suffix = (
                file_path.stem
                .replace(
                    "timber_",
                    "",
                    1,
                )
            )

            if suffix.isdigit():

                highest_index = max(
                    highest_index,
                    int(
                        suffix
                    ),
                )

        return (
            highest_index
            + 1
        )