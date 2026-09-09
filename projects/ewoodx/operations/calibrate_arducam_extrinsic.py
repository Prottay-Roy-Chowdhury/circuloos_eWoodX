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
    ArducamArucoDetector,
    ArducamExtrinsicCalibration,
    ArducamIntrinsicCalibration,
)

from projects.ewoodx.config import (
    CALIBRATION_ROOT,
    ARDUCAM_ARUCO_DICTIONARY,
    ARDUCAM_MARKER_SIZE_MM,
    ARDUCAM_MARKER_WORLD_POSITIONS_MM,
    ARDUCAM_MARKER_OUTER_CORNERS,
)


class EWoodXArducamExtrinsicCalibration:
    """
    eWoodX project operation for Arducam planar
    extrinsic calibration.

    The operation combines reusable framework
    capabilities with the eWoodX-specific ArUco
    marker arrangement and physical coordinates.
    """

    def __init__(
        self,
        intrinsic_file: Path | None = None,
        output_file: Path | None = None,
    ) -> None:

        self.intrinsic_file = (
            Path(intrinsic_file)
            if intrinsic_file is not None
            else (
                CALIBRATION_ROOT
                / "arducam"
                / "intrinsic"
                / "camera_intrinsics.npz"
            )
        )

        self.output_file = (
            Path(output_file)
            if output_file is not None
            else (
                CALIBRATION_ROOT
                / "arducam"
                / "extrinsic"
                / "homography.npz"
            )
        )

        self.dictionary_name = (
            ARDUCAM_ARUCO_DICTIONARY
        )

        self.marker_size_mm = (
            ARDUCAM_MARKER_SIZE_MM
        )

        self.marker_world_positions_mm = (
            ARDUCAM_MARKER_WORLD_POSITIONS_MM
        )

        self.marker_outer_corners = (
            ARDUCAM_MARKER_OUTER_CORNERS
        )

        self.intrinsic_calibration = None

        self.detector = (
            ArducamArucoDetector(
                dictionary_name=(
                    self.dictionary_name
                )
            )
        )

        self.extrinsic_calibration = (
            ArducamExtrinsicCalibration()
        )

        self.detected_markers = None
        self.pixel_points = None
        self.world_points_mm = None

    def run(
        self,
        image_path: Path,
    ) -> ArducamExtrinsicCalibration:
        """
        Run the complete eWoodX Arducam
        extrinsic calibration operation.
        """

        image_path = Path(
            image_path
        )

        print(
            "[eWoodX] Starting Arducam "
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
            "[eWoodX] Arducam extrinsic "
            "calibration complete."
        )

        return (
            self.extrinsic_calibration
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
            ArducamIntrinsicCalibration.load(
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

    image_path = (
        CALIBRATION_ROOT
        / "arducam"
        / "extrinsic"
        / "images"
        / "workspace.jpg"
    )

    operation = (
        EWoodXArducamExtrinsicCalibration()
    )

    operation.run(
        image_path=image_path
    )


if __name__ == "__main__":
    main()