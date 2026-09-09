from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.sensing import (
    ArducamIntrinsicCalibration,
)

from projects.ewoodx.config import (
    CALIBRATION_ROOT,
    ARDUCAM_CHECKERBOARD_INNER_CORNERS,
    ARDUCAM_CHECKERBOARD_SQUARE_SIZE_MM,
)


class EWoodXArducamIntrinsicCalibration:
    """
    eWoodX project operation for Arducam
    intrinsic camera calibration.

    The operation combines the reusable
    Arducam intrinsic calibration capability
    with eWoodX-specific checkerboard settings
    and calibration storage paths.
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
                / "arducam"
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
                / "arducam"
                / "intrinsic"
                / "camera_intrinsics.npz"
            )
        )

        self.checkerboard_inner_corners = (
            ARDUCAM_CHECKERBOARD_INNER_CORNERS
        )

        self.square_size_mm = (
            ARDUCAM_CHECKERBOARD_SQUARE_SIZE_MM
        )

        self.calibration = (
            ArducamIntrinsicCalibration(
                checkerboard_inner_corners=(
                    self.checkerboard_inner_corners
                ),
                square_size_mm=(
                    self.square_size_mm
                ),
            )
        )

        self.image_paths = []

    def run(
        self,
    ) -> ArducamIntrinsicCalibration:
        """
        Run the complete eWoodX Arducam
        intrinsic calibration operation.
        """

        print(
            "[eWoodX] Starting Arducam "
            "intrinsic calibration..."
        )

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

        for image_path in (
            self.image_paths
        ):
            print(
                f"[eWoodX] {image_path}"
            )

        self.calibration.calibrate(
            self.image_paths
        )

        print(
            "[eWoodX] Intrinsic calibration "
            "complete."
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
            "[eWoodX] Intrinsic calibration "
            "saved:"
        )

        print(
            self.output_file
        )

        return (
            self.calibration
        )

    def _find_calibration_images(
        self,
    ) -> list[Path]:
        """
        Find supported calibration images
        inside the configured intrinsic
        calibration image directory.
        """

        if not (
            self.calibration_images_directory
            .exists()
        ):
            raise FileNotFoundError(
                "Intrinsic calibration image "
                "directory not found: "
                f"{self.calibration_images_directory}"
            )

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

        if not image_paths:
            raise RuntimeError(
                "No intrinsic calibration "
                "images found in: "
                f"{self.calibration_images_directory}"
            )

        return image_paths


def main() -> None:

    operation = (
        EWoodXArducamIntrinsicCalibration()
    )

    operation.run()


if __name__ == "__main__":
    main()