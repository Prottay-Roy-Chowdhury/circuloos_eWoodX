from pathlib import Path
import sys

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
    ANGETUBE_MARKER_SIZE_MM,
    ANGETUBE_MARKER_WORLD_POSITIONS_MM,
    ANGETUBE_MARKER_OUTER_CORNERS,
)


class EWoodXAngetubeExtrinsicCalibration:
    """
    eWoodX project operation for Angetube webcam
    planar extrinsic calibration.

    The operation provides interactive capture
    of the physical reference surface and combines
    reusable framework capabilities with the
    eWoodX-specific ArUco marker arrangement and
    physical coordinates.
    """

    def __init__(
        self,
        intrinsic_file: Path | None = None,
        calibration_image: Path | None = None,
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

        self.calibration_image = (
            Path(calibration_image)
            if calibration_image is not None
            else (
                CALIBRATION_ROOT
                / "webcam_angetube"
                / "extrinsic"
                / "images"
                / "workspace.jpg"
            )
        )

        self.output_file = (
            Path(output_file)
            if output_file is not None
            else (
                CALIBRATION_ROOT
                / "webcam_angetube"
                / "extrinsic"
                / "homography.npz"
            )
        )

        self.dictionary_name = (
            ANGETUBE_ARUCO_DICTIONARY
        )

        self.marker_size_mm = (
            ANGETUBE_MARKER_SIZE_MM
        )

        self.marker_world_positions_mm = (
            ANGETUBE_MARKER_WORLD_POSITIONS_MM
        )

        self.marker_outer_corners = (
            ANGETUBE_MARKER_OUTER_CORNERS
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

        self.detector = (
            AngetubeArucoDetector(
                dictionary_name=(
                    self.dictionary_name
                )
            )
        )

        self.extrinsic_calibration = (
            AngetubeExtrinsicCalibration()
        )

        self.detected_markers = None
        self.pixel_points = None
        self.world_points_mm = None

    def capture_image(
        self,
    ) -> Path:
        """
        Interactively capture the eWoodX
        extrinsic calibration image.

        SPACE = capture image and continue
        ENTER = exit without calibration
        """

        self.calibration_image.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

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

        print(
            "[eWoodX] Place the reference surface "
            "and all expected ArUco markers in view."
        )

        print(
            "[eWoodX] SPACE = capture and calibrate"
        )

        print(
            "[eWoodX] ENTER = exit"
        )

        try:

            while True:

                frame = (
                    self.camera.capture()
                )

                cv2.imshow(
                    "eWoodX Angetube Extrinsic Calibration",
                    frame,
                )

                key = (
                    cv2.waitKey(1)
                    & 0xFF
                )

                if key == 32:

                    success = (
                        cv2.imwrite(
                            str(
                                self.calibration_image
                            ),
                            frame,
                            [
                                cv2.IMWRITE_JPEG_QUALITY,
                                100,
                            ],
                        )
                    )

                    if not success:
                        raise RuntimeError(
                            "Could not save extrinsic "
                            "calibration image: "
                            f"{self.calibration_image}"
                        )

                    print(
                        "[eWoodX] Extrinsic calibration "
                        "image saved:"
                    )

                    print(
                        self.calibration_image
                    )

                    return (
                        self.calibration_image
                    )

                elif key in (
                    10,
                    13,
                ):

                    print(
                        "[eWoodX] Extrinsic calibration "
                        "cancelled."
                    )

                    raise KeyboardInterrupt(
                        "Extrinsic calibration cancelled."
                    )

        finally:

            self.camera.close()

            cv2.destroyAllWindows()

    def calibrate(
        self,
        image_path: Path | None = None,
    ) -> AngetubeExtrinsicCalibration:
        """
        Calculate the eWoodX Angetube
        extrinsic calibration from a captured
        or existing calibration image.
        """

        if image_path is None:
            image_path = (
                self.calibration_image
            )

        image_path = Path(
            image_path
        )

        print(
            "[eWoodX] Starting Angetube "
            "extrinsic calibration..."
        )

        image = self._load_image(
            image_path
        )

        self._load_intrinsic_calibration()

        undistorted_image = (
            self.intrinsic_calibration.undistort(
                image
            )
        )

        self.detected_markers = (
            self.detector.detect(
                undistorted_image
            )
        )

        print(
            "[eWoodX] Detected marker IDs:"
        )

        print(
            sorted(
                self.detected_markers.keys()
            )
        )

        (
            self.pixel_points,
            self.world_points_mm,
        ) = self._build_correspondences(
            self.detected_markers
        )

        print(
            "[eWoodX] Pixel points:"
        )

        print(
            self.pixel_points
        )

        print(
            "[eWoodX] World points (mm):"
        )

        print(
            self.world_points_mm
        )

        self.extrinsic_calibration.calibrate(
            pixel_points=(
                self.pixel_points
            ),
            world_points_mm=(
                self.world_points_mm
            ),
        )

        print(
            "[eWoodX] Homography:"
        )

        print(
            self.extrinsic_calibration.homography
        )

        print(
            "[eWoodX] Reprojection errors (mm):"
        )

        print(
            self.extrinsic_calibration
            .reprojection_errors_mm
        )

        self.extrinsic_calibration.save(
            self.output_file
        )

        print(
            "[eWoodX] Extrinsic calibration saved:"
        )

        print(
            self.output_file
        )

        print(
            "[eWoodX] Angetube extrinsic "
            "calibration complete."
        )

        return (
            self.extrinsic_calibration
        )

    def run(
        self,
    ) -> AngetubeExtrinsicCalibration:
        """
        Capture the physical reference surface
        interactively and then perform the
        complete extrinsic calibration.
        """

        image_path = (
            self.capture_image()
        )

        return (
            self.calibrate(
                image_path=image_path
            )
        )

    def _load_image(
        self,
        image_path: Path,
    ) -> np.ndarray:

        if not image_path.exists():
            raise FileNotFoundError(
                f"Calibration image not found: "
                f"{image_path}"
            )

        image = cv2.imread(
            str(image_path)
        )

        if image is None:
            raise RuntimeError(
                f"Could not read calibration image: "
                f"{image_path}"
            )

        return image

    def _load_intrinsic_calibration(
        self,
    ) -> None:

        if not self.intrinsic_file.exists():
            raise FileNotFoundError(
                "Intrinsic calibration file "
                f"not found: "
                f"{self.intrinsic_file}"
            )

        self.intrinsic_calibration = (
            AngetubeIntrinsicCalibration.load(
                self.intrinsic_file
            )
        )

    def _build_correspondences(
        self,
        detected_markers: dict,
    ) -> tuple[
        np.ndarray,
        np.ndarray,
    ]:
        """
        Convert detected ArUco markers into
        eWoodX-specific pixel/world point pairs.
        """

        expected_ids = set(
            self.marker_world_positions_mm.keys()
        )

        detected_ids = set(
            detected_markers.keys()
        )

        missing_ids = (
            expected_ids
            - detected_ids
        )

        if missing_ids:
            raise RuntimeError(
                "Missing expected ArUco markers: "
                f"{sorted(missing_ids)}"
            )

        pixel_points = []
        world_points_mm = []

        for marker_id, world_position in (
            self.marker_world_positions_mm.items()
        ):

            marker_corners = np.asarray(
                detected_markers[
                    marker_id
                ],
                dtype=np.float32,
            )

            if marker_corners.shape != (
                4,
                2,
            ):
                raise RuntimeError(
                    f"Marker {marker_id} corners "
                    "must have shape (4, 2)."
                )

            if marker_id not in (
                self.marker_outer_corners
            ):
                raise RuntimeError(
                    "No outer corner configured "
                    f"for marker {marker_id}."
                )

            corner_index = (
                self.marker_outer_corners[
                    marker_id
                ]
            )

            if corner_index not in (
                0,
                1,
                2,
                3,
            ):
                raise RuntimeError(
                    "Invalid corner index "
                    f"{corner_index} for "
                    f"marker {marker_id}."
                )

            pixel_point = (
                marker_corners[
                    corner_index
                ]
            )

            pixel_points.append(
                pixel_point
            )

            world_points_mm.append(
                world_position
            )

        return (
            np.asarray(
                pixel_points,
                dtype=np.float32,
            ),
            np.asarray(
                world_points_mm,
                dtype=np.float32,
            ),
        )


def main() -> None:

    operation = (
        EWoodXAngetubeExtrinsicCalibration()
    )

    operation.run()


if __name__ == "__main__":
    main()