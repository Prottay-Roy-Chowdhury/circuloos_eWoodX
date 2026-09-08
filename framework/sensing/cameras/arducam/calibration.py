"""
Intrinsic calibration for the Arducam camera setup.
"""

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


class ArducamIntrinsicCalibration:
    """
    Intrinsic camera calibration using a checkerboard pattern.

    This class is responsible for:
    - checkerboard corner detection
    - intrinsic camera calibration
    - storing calibration results
    - saving/loading calibration data
    - image undistortion
    """

    def __init__(
        self,
        checkerboard_inner_corners: tuple[int, int],
        square_size_mm: float,
    ):
        cols, rows = checkerboard_inner_corners

        if cols <= 0 or rows <= 0:
            raise ValueError(
                "checkerboard_inner_corners must contain positive values."
            )

        if square_size_mm <= 0:
            raise ValueError(
                "square_size_mm must be greater than zero."
            )

        self.checkerboard_inner_corners = (
            int(cols),
            int(rows),
        )

        self.square_size_mm = float(
            square_size_mm
        )

        self.camera_matrix: np.ndarray | None = None
        self.dist_coeffs: np.ndarray | None = None
        self.image_size: tuple[int, int] | None = None
        self.rms_error: float | None = None

        self.accepted_images = 0
        self.total_images = 0

    @property
    def is_calibrated(self) -> bool:
        return (
            self.camera_matrix is not None
            and self.dist_coeffs is not None
            and self.image_size is not None
            and self.rms_error is not None
        )

    def calibrate(
        self,
        image_paths: Iterable[str | Path],
    ) -> None:
        """
        Calibrate the camera from checkerboard images.
        """

        paths = [
            Path(path)
            for path in image_paths
        ]

        if not paths:
            raise ValueError(
                "No calibration images provided."
            )

        cols, rows = (
            self.checkerboard_inner_corners
        )

        object_points_template = np.zeros(
            (cols * rows, 3),
            dtype=np.float32,
        )

        object_points_template[:, :2] = (
            np.mgrid[
                0:cols,
                0:rows,
            ]
            .T
            .reshape(-1, 2)
            * self.square_size_mm
        )

        object_points = []
        image_points = []

        criteria = (
            cv2.TERM_CRITERIA_EPS
            + cv2.TERM_CRITERIA_MAX_ITER,
            30,
            0.001,
        )

        image_size = None
        accepted = 0

        for path in paths:
            image = cv2.imread(
                str(path)
            )

            if image is None:
                continue

            gray = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY,
            )

            current_image_size = (
                gray.shape[1],
                gray.shape[0],
            )

            if image_size is None:
                image_size = (
                    current_image_size
                )

            elif current_image_size != image_size:
                raise ValueError(
                    "All calibration images must "
                    "have the same resolution."
                )

            found, corners = (
                cv2.findChessboardCorners(
                    gray,
                    (cols, rows),
                    None,
                )
            )

            if not found:
                continue

            corners_refined = (
                cv2.cornerSubPix(
                    gray,
                    corners,
                    (11, 11),
                    (-1, -1),
                    criteria,
                )
            )

            object_points.append(
                object_points_template.copy()
            )

            image_points.append(
                corners_refined
            )

            accepted += 1

        self.total_images = len(paths)
        self.accepted_images = accepted

        if accepted == 0:
            raise RuntimeError(
                "Checkerboard could not be detected "
                "in any calibration image."
            )

        (
            rms_error,
            camera_matrix,
            dist_coeffs,
            _,
            _,
        ) = cv2.calibrateCamera(
            object_points,
            image_points,
            image_size,
            None,
            None,
        )

        self.camera_matrix = (
            camera_matrix
        )

        self.dist_coeffs = (
            dist_coeffs
        )

        self.image_size = (
            image_size
        )

        self.rms_error = float(
            rms_error
        )

    def undistort(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """
        Return an undistorted image.
        """

        if not self.is_calibrated:
            raise RuntimeError(
                "Camera calibration is not available."
            )

        return cv2.undistort(
            image,
            self.camera_matrix,
            self.dist_coeffs,
        )

    def save(
        self,
        file_path: str | Path,
    ) -> None:
        """
        Save calibration data to an NPZ file.
        """

        if not self.is_calibrated:
            raise RuntimeError(
                "Camera calibration is not available."
            )

        path = Path(
            file_path
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        np.savez(
            path,
            camera_matrix=self.camera_matrix,
            dist_coeffs=self.dist_coeffs,
            image_size=np.asarray(
                self.image_size,
                dtype=np.int32,
            ),
            rms_error=self.rms_error,
            checkerboard_inner_corners=np.asarray(
                self.checkerboard_inner_corners,
                dtype=np.int32,
            ),
            square_size_mm=self.square_size_mm,
        )

    @classmethod
    def load(
        cls,
        file_path: str | Path,
    ) -> "ArducamIntrinsicCalibration":
        """
        Load calibration data from an NPZ file.
        """

        path = Path(
            file_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Calibration file not found: {path}"
            )

        with np.load(
            path,
            allow_pickle=False,
        ) as data:

            checkerboard_inner_corners = tuple(
                int(value)
                for value
                in data[
                    "checkerboard_inner_corners"
                ]
            )

            square_size_mm = float(
                data["square_size_mm"]
            )

            calibration = cls(
                checkerboard_inner_corners=(
                    checkerboard_inner_corners
                ),
                square_size_mm=(
                    square_size_mm
                ),
            )

            calibration.camera_matrix = (
                data[
                    "camera_matrix"
                ].copy()
            )

            calibration.dist_coeffs = (
                data[
                    "dist_coeffs"
                ].copy()
            )

            calibration.image_size = tuple(
                int(value)
                for value
                in data[
                    "image_size"
                ]
            )

            calibration.rms_error = float(
                data[
                    "rms_error"
                ]
            )

        return calibration