from pathlib import Path

import cv2
import numpy as np


class ArducamExtrinsicCalibration:
    """
    Homography-based extrinsic calibration for a planar
    physical reference surface.

    The calibration maps image pixel coordinates to
    physical coordinates in millimetres.
    """

    def __init__(self) -> None:

        self.homography = None
        self.reprojection_errors_mm = None

    @property
    def is_calibrated(self) -> bool:
        return self.homography is not None

    def calibrate(
        self,
        pixel_points,
        world_points_mm,
    ):

        pixel_points = np.asarray(
            pixel_points,
            dtype=np.float32,
        )

        world_points_mm = np.asarray(
            world_points_mm,
            dtype=np.float32,
        )

        self._validate_points(
            pixel_points,
            world_points_mm,
        )

        homography, _ = cv2.findHomography(
            pixel_points,
            world_points_mm,
            method=0,
        )

        if homography is None:
            raise RuntimeError(
                "Could not calculate homography."
            )

        self.homography = homography

        reprojected = self.transform_points(
            pixel_points
        )

        self.reprojection_errors_mm = (
            np.linalg.norm(
                reprojected
                - world_points_mm,
                axis=1,
            )
        )

        return self.homography

    def transform_points(
        self,
        pixel_points,
    ):

        if not self.is_calibrated:
            raise RuntimeError(
                "Extrinsic calibration has not "
                "been computed or loaded."
            )

        pixel_points = np.asarray(
            pixel_points,
            dtype=np.float32,
        )

        if (
            pixel_points.ndim != 2
            or pixel_points.shape[1] != 2
        ):
            raise ValueError(
                "pixel_points must have shape (N, 2)."
            )

        transformed = cv2.perspectiveTransform(
            pixel_points.reshape(
                -1,
                1,
                2,
            ),
            self.homography,
        )

        return transformed.reshape(
            -1,
            2,
        )

    def save(
        self,
        file_path,
    ) -> None:

        if not self.is_calibrated:
            raise RuntimeError(
                "Extrinsic calibration has not "
                "been computed."
            )

        file_path = Path(
            file_path
        )

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        np.savez(
            file_path,
            homography=self.homography,
        )

    @classmethod
    def load(
        cls,
        file_path,
    ):

        file_path = Path(
            file_path
        )

        if not file_path.exists():
            raise FileNotFoundError(
                f"Calibration file not found: "
                f"{file_path}"
            )

        data = np.load(
            file_path
        )

        calibration = cls()

        calibration.homography = (
            data["homography"]
        )

        return calibration

    @staticmethod
    def _validate_points(
        pixel_points,
        world_points_mm,
    ) -> None:

        if (
            pixel_points.ndim != 2
            or pixel_points.shape[1] != 2
        ):
            raise ValueError(
                "pixel_points must have shape (N, 2)."
            )

        if (
            world_points_mm.ndim != 2
            or world_points_mm.shape[1] != 2
        ):
            raise ValueError(
                "world_points_mm must have "
                "shape (N, 2)."
            )

        if (
            len(pixel_points)
            != len(world_points_mm)
        ):
            raise ValueError(
                "pixel_points and world_points_mm "
                "must contain the same number "
                "of points."
            )

        if len(pixel_points) < 4:
            raise ValueError(
                "At least four point "
                "correspondences are required."
            )