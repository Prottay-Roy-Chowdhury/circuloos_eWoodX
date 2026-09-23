from pathlib import Path
import sys
import time

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
    AngetubeIntrinsicCalibration,
    AngetubeExtrinsicCalibration,
)

from projects.ewoodx.config import (
    CALIBRATION_ROOT,
    TABLE_WIDTH_MM,
    TABLE_HEIGHT_MM,

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

    PROJECTOR_WIDTH,
    PROJECTOR_HEIGHT,
    PROJECTOR_SCREEN_ORIGIN_X,
    PROJECTOR_SCREEN_ORIGIN_Y,
)


class EWoodXProjectorAutoCalibration:
    """
    eWoodX automatic projector calibration.

    Projector pixels are projected as bright dots,
    detected by the calibrated Angetube camera,
    transformed into workspace coordinates, and
    used to calculate the world-to-projector
    homography.
    """

    PROJECTOR_WINDOW = (
        "eWoodX Projector Calibration"
    )

    DEBUG_CAMERA_WINDOW = (
        "Camera Dot Detection"
    )

    DEBUG_THRESHOLD_WINDOW = (
        "Difference Threshold"
    )

    DOT_RADIUS = 25

    SETTLE_TIME = 0.45

    DISCARD_FRAMES = 5

    BRIGHTNESS_THRESHOLD = 40

    MIN_BLOB_AREA = 40

    MAX_BLOB_AREA = 8000

    MIN_CIRCULARITY = 0.25

    WORLD_MARGIN_MM = 100.0

    def __init__(
        self,
        intrinsic_file: Path | None = None,
        extrinsic_file: Path | None = None,
        output_file: Path | None = None,
    ) -> None:

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

        self.extrinsic_file = (
            Path(extrinsic_file)
            if extrinsic_file is not None
            else (
                CALIBRATION_ROOT
                / "webcam_angetube"
                / "extrinsic"
                / "homography.npz"
            )
        )

        self.output_file = (
            Path(output_file)
            if output_file is not None
            else (
                CALIBRATION_ROOT
                / "projector"
                / "automatic"
                / "projector_homography.npz"
            )
        )

        self.report_file = (
            self.output_file.with_suffix(
                ".txt"
            )
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

        self.intrinsic_calibration = None
        self.extrinsic_calibration = None

        self.projector_points = (
            self._create_projector_points()
        )

        self.detected_camera_points = []
        self.detected_world_points = []
        self.valid_projector_points = []

    # -----------------------------------------------------------------
    # Projector calibration grid
    # -----------------------------------------------------------------

    def _create_projector_points(
        self,
    ) -> np.ndarray:

        projector_x_points = (
            np.linspace(
                int(
                    PROJECTOR_WIDTH
                    * 0.10
                ),
                int(
                    PROJECTOR_WIDTH
                    * 0.90
                ),
                5,
            )
            .astype(int)
            .tolist()
        )

        projector_y_points = (
            np.linspace(
                int(
                    PROJECTOR_HEIGHT
                    * 0.15
                ),
                int(
                    PROJECTOR_HEIGHT
                    * 0.85
                ),
                4,
            )
            .astype(int)
            .tolist()
        )

        return np.array(
            [
                [x, y]
                for y in projector_y_points
                for x in projector_x_points
            ],
            dtype=np.float32,
        )

    # -----------------------------------------------------------------
    # Calibration loading
    # -----------------------------------------------------------------

    def _load_calibrations(
        self,
    ) -> None:

        if not self.intrinsic_file.exists():

            raise FileNotFoundError(
                "Camera calibration not found:\n"
                f"{self.intrinsic_file}"
            )

        if not self.extrinsic_file.exists():

            raise FileNotFoundError(
                "Workspace homography not found:\n"
                f"{self.extrinsic_file}"
            )

        self.intrinsic_calibration = (
            AngetubeIntrinsicCalibration.load(
                self.intrinsic_file
            )
        )

        self.extrinsic_calibration = (
            AngetubeExtrinsicCalibration.load(
                self.extrinsic_file
            )
        )

        print()
        print(
            "=========================================="
        )

        print(
            "Loading existing eWoodX calibration"
        )

        print(
            "=========================================="
        )

        print()

        print(
            "Camera matrix:"
        )

        print(
            self.intrinsic_calibration
            .camera_matrix
        )

        print()

        print(
            "Camera distortion:"
        )

        print(
            self.intrinsic_calibration
            .dist_coeffs
        )

        print()

        print(
            "Calibration image size:",
            self.intrinsic_calibration
            .image_size,
        )

        print()

        print(
            "Camera -> World homography:"
        )

        print(
            self.extrinsic_calibration
            .homography
        )

        print()

    # -----------------------------------------------------------------
    # Projector drawing
    # -----------------------------------------------------------------

    def _create_black_canvas(
        self,
    ) -> np.ndarray:

        return np.zeros(
            (
                PROJECTOR_HEIGHT,
                PROJECTOR_WIDTH,
                3,
            ),
            dtype=np.uint8,
        )

    def _show_black(
        self,
    ) -> None:

        canvas = (
            self._create_black_canvas()
        )

        cv2.imshow(
            self.PROJECTOR_WINDOW,
            canvas,
        )

        cv2.waitKey(1)

    def _show_dot(
        self,
        x,
        y,
    ) -> None:

        canvas = (
            self._create_black_canvas()
        )

        cv2.circle(
            canvas,
            (
                int(x),
                int(y),
            ),
            self.DOT_RADIUS,
            (
                255,
                255,
                255,
            ),
            -1,
            cv2.LINE_AA,
        )

        cv2.imshow(
            self.PROJECTOR_WINDOW,
            canvas,
        )

        cv2.waitKey(1)

    # -----------------------------------------------------------------
    # Camera capture
    # -----------------------------------------------------------------

    def _capture_frame(
        self,
    ) -> np.ndarray:
        """
        Capture a digitally zoomed frame through
        AngetubeCamera and undistort it using the
        existing intrinsic calibration.

        This reproduces the reference sequence:
        raw -> digital zoom -> undistort.
        """

        for _ in range(
            self.DISCARD_FRAMES
        ):

            self.camera.capture()

        frame = (
            self.camera.capture()
        )

        return (
            self.intrinsic_calibration
            .undistort(
                frame
            )
        )

    # -----------------------------------------------------------------
    # Camera pixel -> world
    # -----------------------------------------------------------------

    def _camera_to_world(
        self,
        x_px,
        y_px,
    ) -> tuple[
        float,
        float,
    ]:

        camera_point = np.array(
            [
                [
                    x_px,
                    y_px,
                ]
            ],
            dtype=np.float32,
        )

        world_point = (
            self.extrinsic_calibration
            .transform_points(
                camera_point
            )[0]
        )

        return (
            float(
                world_point[0]
            ),
            float(
                world_point[1]
            ),
        )

    # -----------------------------------------------------------------
    # Detect projected dot
    # -----------------------------------------------------------------

    def _detect_projected_dot(
        self,
        background_frame,
        projected_frame,
    ):

        background_gray = (
            cv2.cvtColor(
                background_frame,
                cv2.COLOR_BGR2GRAY,
            )
        )

        projected_gray = (
            cv2.cvtColor(
                projected_frame,
                cv2.COLOR_BGR2GRAY,
            )
        )

        # Positive difference only.
        difference = cv2.subtract(
            projected_gray,
            background_gray,
        )

        difference_blurred = (
            cv2.GaussianBlur(
                difference,
                (
                    7,
                    7,
                ),
                0,
            )
        )

        _, threshold = (
            cv2.threshold(
                difference_blurred,
                self.BRIGHTNESS_THRESHOLD,
                255,
                cv2.THRESH_BINARY,
            )
        )

        kernel = np.ones(
            (
                3,
                3,
            ),
            np.uint8,
        )

        threshold = (
            cv2.morphologyEx(
                threshold,
                cv2.MORPH_OPEN,
                kernel,
            )
        )

        threshold = (
            cv2.morphologyEx(
                threshold,
                cv2.MORPH_CLOSE,
                kernel,
            )
        )

        contours, _ = (
            cv2.findContours(
                threshold,
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
                < self.MIN_BLOB_AREA
            ):
                continue

            if (
                area
                > self.MAX_BLOB_AREA
            ):
                continue

            perimeter = (
                cv2.arcLength(
                    contour,
                    True,
                )
            )

            if perimeter <= 0:
                continue

            circularity = (
                4.0
                * np.pi
                * area
                / (
                    perimeter
                    * perimeter
                )
            )

            if (
                circularity
                < self.MIN_CIRCULARITY
            ):
                continue

            moments = (
                cv2.moments(
                    contour
                )
            )

            if (
                moments["m00"]
                == 0
            ):
                continue

            cx = (
                moments["m10"]
                / moments["m00"]
            )

            cy = (
                moments["m01"]
                / moments["m00"]
            )

            blob_mask = (
                np.zeros_like(
                    difference
                )
            )

            cv2.drawContours(
                blob_mask,
                [
                    contour
                ],
                -1,
                255,
                -1,
            )

            mean_brightness = (
                cv2.mean(
                    difference,
                    mask=blob_mask,
                )[0]
            )

            candidates.append(
                {
                    "brightness": (
                        mean_brightness
                    ),
                    "circularity": (
                        circularity
                    ),
                    "area": area,
                    "x": cx,
                    "y": cy,
                }
            )

        if not candidates:

            return (
                None,
                threshold,
                difference,
            )

        candidates.sort(
            key=lambda item: (
                item[
                    "brightness"
                ]
            ),
            reverse=True,
        )

        best = (
            candidates[0]
        )

        print(
            "   Candidate:"
            f" brightness="
            f"{best['brightness']:.1f}"
            f" area="
            f"{best['area']:.1f}"
            f" circularity="
            f"{best['circularity']:.2f}"
        )

        return (
            (
                best["x"],
                best["y"],
            ),
            threshold,
            difference,
        )

    # -----------------------------------------------------------------
    # Debug visualization
    # -----------------------------------------------------------------

    def _show_debug(
        self,
        projected_frame,
        threshold,
        dot_position,
        projector_point,
    ) -> None:

        debug_frame = (
            projected_frame.copy()
        )

        if (
            dot_position
            is not None
        ):

            x = int(
                round(
                    dot_position[0]
                )
            )

            y = int(
                round(
                    dot_position[1]
                )
            )

            cv2.circle(
                debug_frame,
                (
                    x,
                    y,
                ),
                35,
                (
                    0,
                    0,
                    255,
                ),
                4,
            )

            cv2.putText(
                debug_frame,
                "DETECTED DOT",
                (
                    x + 45,
                    y,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (
                    0,
                    0,
                    255,
                ),
                2,
                cv2.LINE_AA,
            )

        label = (
            "Projector: "
            f"{int(projector_point[0])}, "
            f"{int(projector_point[1])}"
        )

        cv2.putText(
            debug_frame,
            label,
            (
                60,
                80,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.4,
            (
                0,
                255,
                0,
            ),
            3,
            cv2.LINE_AA,
        )

        debug_small = (
            cv2.resize(
                debug_frame,
                (
                    1280,
                    720,
                ),
            )
        )

        threshold_small = (
            cv2.resize(
                threshold,
                (
                    1280,
                    720,
                ),
            )
        )

        cv2.imshow(
            self.DEBUG_CAMERA_WINDOW,
            debug_small,
        )

        cv2.imshow(
            self.DEBUG_THRESHOLD_WINDOW,
            threshold_small,
        )

        cv2.waitKey(
            100
        )

    # -----------------------------------------------------------------
    # Collect projector/camera/world correspondences
    # -----------------------------------------------------------------

    def _collect_points(
        self,
    ) -> None:

        print()
        print(
            "=========================================="
        )

        print(
            "eWoodX Automatic Projector Calibration"
        )

        print(
            "=========================================="
        )

        print()

        print(
            "Number of projector points: "
            f"{len(self.projector_points)}"
        )

        print()

        self._show_black()

        time.sleep(
            1.0
        )

        for index, projector_point in enumerate(
            self.projector_points,
            start=1,
        ):

            projector_x = int(
                projector_point[0]
            )

            projector_y = int(
                projector_point[1]
            )

            print()

            print(
                f"[{index:02d}/"
                f"{len(self.projector_points)}]"
            )

            print(
                "   Projector pixel: "
                f"({projector_x}, "
                f"{projector_y})"
            )

            # ---------------------------------------------------------
            # Black background
            # ---------------------------------------------------------

            self._show_black()

            time.sleep(
                self.SETTLE_TIME
            )

            background_frame = (
                self._capture_frame()
            )

            # ---------------------------------------------------------
            # Project white dot
            # ---------------------------------------------------------

            self._show_dot(
                projector_x,
                projector_y,
            )

            time.sleep(
                self.SETTLE_TIME
            )

            projected_frame = (
                self._capture_frame()
            )

            # ---------------------------------------------------------
            # Detect projected dot
            # ---------------------------------------------------------

            (
                dot_position,
                threshold,
                difference,
            ) = (
                self._detect_projected_dot(
                    background_frame,
                    projected_frame,
                )
            )

            self._show_debug(
                projected_frame,
                threshold,
                dot_position,
                projector_point,
            )

            if (
                dot_position
                is None
            ):

                print(
                    "   FAILED: "
                    "projected dot not detected."
                )

                continue

            camera_x = float(
                dot_position[0]
            )

            camera_y = float(
                dot_position[1]
            )

            world_x, world_y = (
                self._camera_to_world(
                    camera_x,
                    camera_y,
                )
            )

            print(
                "   Camera pixel: "
                f"({camera_x:.1f}, "
                f"{camera_y:.1f})"
            )

            print(
                "   World mm: "
                f"({world_x:.1f}, "
                f"{world_y:.1f})"
            )

            if not (
                -self.WORLD_MARGIN_MM
                <= world_x
                <= TABLE_WIDTH_MM
                + self.WORLD_MARGIN_MM
            ):

                print(
                    "   FAILED: "
                    "X coordinate outside "
                    "workspace."
                )

                continue

            if not (
                -self.WORLD_MARGIN_MM
                <= world_y
                <= TABLE_HEIGHT_MM
                + self.WORLD_MARGIN_MM
            ):

                print(
                    "   FAILED: "
                    "Y coordinate outside "
                    "workspace."
                )

                continue

            self.detected_camera_points.append(
                [
                    camera_x,
                    camera_y,
                ]
            )

            self.detected_world_points.append(
                [
                    world_x,
                    world_y,
                ]
            )

            self.valid_projector_points.append(
                [
                    projector_x,
                    projector_y,
                ]
            )

        self._show_black()

    # -----------------------------------------------------------------
    # Calculate homography
    # -----------------------------------------------------------------

    def _calculate_homography(
        self,
    ):

        camera_points = np.array(
            self.detected_camera_points,
            dtype=np.float32,
        )

        world_points = np.array(
            self.detected_world_points,
            dtype=np.float32,
        )

        projector_points = np.array(
            self.valid_projector_points,
            dtype=np.float32,
        )

        print()
        print(
            "=========================================="
        )

        print(
            "Calibration collection finished"
        )

        print(
            "=========================================="
        )

        print(
            "Valid detections: "
            f"{len(world_points)} / "
            f"{len(self.projector_points)}"
        )

        print()

        if (
            len(world_points)
            < 4
        ):

            raise RuntimeError(
                "Not enough valid "
                "calibration points."
            )

        (
            homography,
            mask,
        ) = cv2.findHomography(
            world_points,
            projector_points,
            cv2.RANSAC,
            4.0,
        )

        if homography is None:

            raise RuntimeError(
                "Could not calculate "
                "world-to-projector homography."
            )

        if mask is not None:

            inlier_mask = (
                mask.ravel()
                == 1
            )

            inlier_count = int(
                np.sum(
                    inlier_mask
                )
            )

        else:

            inlier_mask = (
                np.ones(
                    len(
                        world_points
                    ),
                    dtype=bool,
                )
            )

            inlier_count = len(
                world_points
            )

        print(
            "RANSAC inliers: "
            f"{inlier_count} / "
            f"{len(world_points)}"
        )

        print()

        predicted_projector_points = (
            cv2.perspectiveTransform(
                world_points.reshape(
                    -1,
                    1,
                    2,
                ),
                homography,
            )
            .reshape(
                -1,
                2,
            )
        )

        errors = (
            np.linalg.norm(
                predicted_projector_points
                - projector_points,
                axis=1,
            )
        )

        mean_error_all = float(
            np.mean(
                errors
            )
        )

        max_error_all = float(
            np.max(
                errors
            )
        )

        inlier_errors = (
            errors[
                inlier_mask
            ]
        )

        mean_error_inliers = float(
            np.mean(
                inlier_errors
            )
        )

        max_error_inliers = float(
            np.max(
                inlier_errors
            )
        )

        print()
        print(
            "World -> Projector Homography:"
        )

        print()

        print(
            homography
        )

        print()

        print(
            "Mean error - all points: "
            f"{mean_error_all:.3f} px"
        )

        print(
            "Maximum error - all points: "
            f"{max_error_all:.3f} px"
        )

        print()

        print(
            "Mean error - RANSAC inliers: "
            f"{mean_error_inliers:.3f} px"
        )

        print(
            "Maximum error - RANSAC inliers: "
            f"{max_error_inliers:.3f} px"
        )

        return {
            "homography": homography,
            "camera_points": camera_points,
            "world_points": world_points,
            "projector_points": projector_points,
            "inlier_mask": inlier_mask,
            "inlier_count": inlier_count,
            "errors": errors,
            "mean_error_all": mean_error_all,
            "max_error_all": max_error_all,
            "mean_error_inliers": (
                mean_error_inliers
            ),
            "max_error_inliers": (
                max_error_inliers
            ),
        }

    # -----------------------------------------------------------------
    # Save calibration
    # -----------------------------------------------------------------

    def _save_calibration(
        self,
        result,
    ) -> None:

        self.output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        np.savez(
            self.output_file,
            H_world_to_projector=(
                result[
                    "homography"
                ]
            ),
            camera_points_px=(
                result[
                    "camera_points"
                ]
            ),
            world_points_mm=(
                result[
                    "world_points"
                ]
            ),
            projector_points_px=(
                result[
                    "projector_points"
                ]
            ),
            ransac_inlier_mask=(
                result[
                    "inlier_mask"
                ]
            ),
            reprojection_errors_px=(
                result[
                    "errors"
                ]
            ),
            mean_error_all_px=(
                result[
                    "mean_error_all"
                ]
            ),
            max_error_all_px=(
                result[
                    "max_error_all"
                ]
            ),
            mean_error_inlier_px=(
                result[
                    "mean_error_inliers"
                ]
            ),
            max_error_inlier_px=(
                result[
                    "max_error_inliers"
                ]
            ),
            projector_resolution=(
                np.array(
                    [
                        PROJECTOR_WIDTH,
                        PROJECTOR_HEIGHT,
                    ]
                )
            ),
        )

        with self.report_file.open(
            "w",
            encoding="utf-8",
        ) as report:

            report.write(
                "eWoodX PROJECTOR CALIBRATION\n"
            )

            report.write(
                "=" * 55
                + "\n\n"
            )

            report.write(
                "Valid detected points: "
                f"{len(result['world_points'])}\n"
            )

            report.write(
                "RANSAC inliers: "
                f"{result['inlier_count']}\n\n"
            )

            report.write(
                "Projector resolution: "
                f"{PROJECTOR_WIDTH} x "
                f"{PROJECTOR_HEIGHT}\n\n"
            )

            report.write(
                "World -> Projector Homography:\n"
            )

            report.write(
                np.array2string(
                    result[
                        "homography"
                    ],
                    precision=10,
                )
            )

            report.write(
                "\n\n"
            )

            report.write(
                "Mean error - all: "
                f"{result['mean_error_all']:.4f} px\n"
            )

            report.write(
                "Max error - all: "
                f"{result['max_error_all']:.4f} px\n"
            )

            report.write(
                "Mean error - inliers: "
                f"{result['mean_error_inliers']:.4f} px\n"
            )

            report.write(
                "Max error - inliers: "
                f"{result['max_error_inliers']:.4f} px\n"
            )

            report.write(
                "\nCalibration Points:\n"
            )

            for index in range(
                len(
                    result[
                        "world_points"
                    ]
                )
            ):

                world = (
                    result[
                        "world_points"
                    ][index]
                )

                projector = (
                    result[
                        "projector_points"
                    ][index]
                )

                camera_point = (
                    result[
                        "camera_points"
                    ][index]
                )

                error = (
                    result[
                        "errors"
                    ][index]
                )

                status = (
                    "INLIER"
                    if result[
                        "inlier_mask"
                    ][index]
                    else "OUTLIER"
                )

                report.write(
                    f"P{index + 1:02d}: "
                    "Camera=("
                    f"{camera_point[0]:.2f}, "
                    f"{camera_point[1]:.2f}) px   "
                    "World=("
                    f"{world[0]:.2f}, "
                    f"{world[1]:.2f}) mm   "
                    "Projector=("
                    f"{projector[0]:.0f}, "
                    f"{projector[1]:.0f}) px   "
                    "Error="
                    f"{error:.3f} px   "
                    f"{status}\n"
                )

        print()
        print(
            "=========================================="
        )

        print(
            "Calibration complete"
        )

        print(
            "=========================================="
        )

        print()

        print(
            "Saved NPZ:"
        )

        print(
            self.output_file
        )

        print()

        print(
            "Saved report:"
        )

        print(
            self.report_file
        )

        print()

        print(
            "IMPORTANT:"
        )

        print(
            "Watch the debug red circle "
            "during calibration."
        )

        print(
            "It must follow the projected "
            "white dot."
        )

    # -----------------------------------------------------------------
    # Run
    # -----------------------------------------------------------------

    def run(
        self,
    ) -> None:

        self._load_calibrations()

        print(
            "[eWoodX] Opening Angetube camera..."
        )

        self.camera.open()

        print(
            "[eWoodX] Camera opened."
        )

        print(
            "[eWoodX] Camera resolution:"
        )

        print(
            self.camera.resolution
        )

        cv2.namedWindow(
            self.PROJECTOR_WINDOW,
            cv2.WINDOW_NORMAL,
        )

        cv2.moveWindow(
            self.PROJECTOR_WINDOW,
            PROJECTOR_SCREEN_ORIGIN_X,
            PROJECTOR_SCREEN_ORIGIN_Y,
        )

        cv2.setWindowProperty(
            self.PROJECTOR_WINDOW,
            cv2.WND_PROP_FULLSCREEN,
            cv2.WINDOW_FULLSCREEN,
        )

        try:

            self._collect_points()

            result = (
                self._calculate_homography()
            )

            self._save_calibration(
                result
            )

        finally:

            self.camera.close()

            cv2.destroyAllWindows()


def main() -> None:

    operation = (
        EWoodXProjectorAutoCalibration()
    )

    operation.run()


if __name__ == "__main__":
    main()