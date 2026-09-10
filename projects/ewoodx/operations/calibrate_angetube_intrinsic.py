from pathlib import Path
import sys

import cv2


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

    ANGETUBE_CHECKERBOARD_INNER_CORNERS,
    ANGETUBE_CHECKERBOARD_SQUARE_SIZE_MM,

    ANGETUBE_CALIBRATION_MODEL,
    ANGETUBE_FISHEYE_BALANCE,
    ANGETUBE_FISHEYE_FOV_SCALE,
    ANGETUBE_FISHEYE_CHECK_COND,
    ANGETUBE_FISHEYE_RECOMPUTE_EXTRINSIC,
    ANGETUBE_FISHEYE_FIX_SKEW,
)


class EWoodXAngetubeIntrinsicCalibration:
    """
    eWoodX project operation for Angetube webcam
    intrinsic camera calibration.

    The operation provides interactive
    checkerboard image capture followed by
    intrinsic calibration using the reusable
    Angetube framework capabilities.
    """

    def __init__(
        self,
        calibration_images_directory: Path | None = None,
        output_file: Path | None = None,
    ) -> None:

        self.calibration_images_directory = (
            Path(
                calibration_images_directory
            )
            if calibration_images_directory
            is not None
            else (
                CALIBRATION_ROOT
                / "webcam_angetube"
                / "intrinsic"
                / "images"
            )
        )

        self.output_file = (
            Path(
                output_file
            )
            if output_file is not None
            else (
                CALIBRATION_ROOT
                / "webcam_angetube"
                / "intrinsic"
                / "camera_intrinsics.npz"
            )
        )

        self.checkerboard_inner_corners = (
            ANGETUBE_CHECKERBOARD_INNER_CORNERS
        )

        self.square_size_mm = (
            ANGETUBE_CHECKERBOARD_SQUARE_SIZE_MM
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

        self.calibration = (
            AngetubeIntrinsicCalibration(
                checkerboard_inner_corners=(
                    self.checkerboard_inner_corners
                ),
                square_size_mm=(
                    self.square_size_mm
                ),
                calibration_model=(
                    ANGETUBE_CALIBRATION_MODEL
                ),
                fisheye_balance=(
                    ANGETUBE_FISHEYE_BALANCE
                ),
                fisheye_fov_scale=(
                    ANGETUBE_FISHEYE_FOV_SCALE
                ),
                fisheye_check_cond=(
                    ANGETUBE_FISHEYE_CHECK_COND
                ),
                fisheye_recompute_extrinsic=(
                    ANGETUBE_FISHEYE_RECOMPUTE_EXTRINSIC
                ),
                fisheye_fix_skew=(
                    ANGETUBE_FISHEYE_FIX_SKEW
                ),
            )
        )

        self.image_paths = []

    def capture_images(
        self,
    ) -> list[Path]:
        """
        Interactively capture checkerboard
        images.

        SPACE = capture image
        ENTER = finish capture
        """

        self.calibration_images_directory.mkdir(
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
            "[eWoodX] Position the checkerboard "
            "at different locations and angles."
        )

        print(
            "[eWoodX] SPACE = capture image"
        )

        print(
            "[eWoodX] ENTER = finish capture"
        )

        captured_paths = []

        existing_images = (
            self._find_calibration_images(
                require_images=False
            )
        )

        photo_count = len(
            existing_images
        )

        try:

            while True:

                frame = (
                    self.camera.capture()
                )

                cv2.imshow(
                    "eWoodX Angetube Intrinsic Calibration",
                    frame,
                )

                key = (
                    cv2.waitKey(1)
                    & 0xFF
                )

                if key == 32:

                    photo_count += 1

                    image_path = (
                        self.calibration_images_directory
                        / (
                            "checkerboard_"
                            f"{photo_count:02d}.jpg"
                        )
                    )

                    success = (
                        cv2.imwrite(
                            str(image_path),
                            frame,
                            [
                                cv2.IMWRITE_JPEG_QUALITY,
                                100,
                            ],
                        )
                    )

                    if not success:
                        raise RuntimeError(
                            "Could not save intrinsic "
                            "calibration image: "
                            f"{image_path}"
                        )

                    captured_paths.append(
                        image_path
                    )

                    print(
                        "[eWoodX] Captured:"
                    )

                    print(
                        image_path
                    )

                elif key in (
                    10,
                    13,
                ):

                    print(
                        "[eWoodX] Capture finished."
                    )

                    break

        finally:

            self.camera.close()

            cv2.destroyAllWindows()

        print(
            "[eWoodX] New calibration images "
            "captured:"
        )

        print(
            len(
                captured_paths
            )
        )

        return captured_paths

    def calibrate(
        self,
    ) -> AngetubeIntrinsicCalibration:
        """
        Calculate intrinsic calibration using
        all calibration images currently stored
        in the project calibration directory.
        """

        self.image_paths = (
            self._find_calibration_images()
        )

        print(
            "[eWoodX] Calibration images found:"
        )

        print(
            len(
                self.image_paths
            )
        )

        self.calibration.calibrate(
            self.image_paths
        )

        print(
            "[eWoodX] Calibration model:"
        )

        print(
            ANGETUBE_CALIBRATION_MODEL
        )

        print(
            "[eWoodX] RMS reprojection error:"
        )

        print(
            self.calibration.rms_error
        )

        print(
            "[eWoodX] Accepted images:"
        )

        print(
            self.calibration.accepted_images
        )

        print(
            "[eWoodX] Total images:"
        )

        print(
            self.calibration.total_images
        )

        print(
            "[eWoodX] Camera matrix:"
        )

        print(
            self.calibration.camera_matrix
        )

        print(
            "[eWoodX] Distortion coefficients:"
        )

        print(
            self.calibration.dist_coeffs
        )

        print(
            "[eWoodX] Image size:"
        )

        print(
            self.calibration.image_size
        )

        self.calibration.save(
            self.output_file
        )

        print(
            "[eWoodX] Intrinsic calibration saved:"
        )

        print(
            self.output_file
        )

        return self.calibration

    def run(
        self,
    ) -> AngetubeIntrinsicCalibration:
        """
        Capture calibration images
        interactively and then perform
        intrinsic calibration.
        """

        print(
            "[eWoodX] Starting Angetube "
            "intrinsic calibration..."
        )

        self.capture_images()

        calibration = (
            self.calibrate()
        )

        print(
            "[eWoodX] Angetube intrinsic "
            "calibration complete."
        )

        return calibration

    def _find_calibration_images(
        self,
        require_images: bool = True,
    ) -> list[Path]:

        if not (
            self.calibration_images_directory
            .exists()
        ):

            if require_images:
                raise FileNotFoundError(
                    "Intrinsic calibration image "
                    "directory not found: "
                    f"{self.calibration_images_directory}"
                )

            return []

        supported_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".tif",
            ".tiff",
        }

        image_paths = sorted(
            path
            for path in (
                self.calibration_images_directory
                .iterdir()
            )
            if (
                path.is_file()
                and
                path.suffix.lower()
                in supported_extensions
            )
        )

        if (
            require_images
            and
            not image_paths
        ):
            raise RuntimeError(
                "No intrinsic calibration "
                "images found in: "
                f"{self.calibration_images_directory}"
            )

        return image_paths


def main() -> None:

    operation = (
        EWoodXAngetubeIntrinsicCalibration()
    )

    operation.run()


if __name__ == "__main__":
    main()