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

    def save_text_report(
        self,
        file_path: str | Path,
        pixel_points=None,
        world_points_mm=None,
    ) -> None:
        """
        Save a human-readable planar
        extrinsic calibration report.
        """

        if not self.is_calibrated:
            raise RuntimeError(
                "Extrinsic calibration has not "
                "been computed."
            )

        path = Path(
            file_path
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:

            file.write(
                "ARDUCAM EXTRINSIC CALIBRATION REPORT\n"
            )

            file.write(
                "=" * 50
                + "\n\n"
            )

            if pixel_points is not None:

                pixel_points = np.asarray(
                    pixel_points,
                    dtype=np.float32,
                )

                file.write(
                    "Pixel points:\n"
                )

                file.write(
                    np.array2string(
                        pixel_points,
                        precision=4,
                        suppress_small=True,
                    )
                )

                file.write(
                    "\n\n"
                )

            if world_points_mm is not None:

                world_points_mm = np.asarray(
                    world_points_mm,
                    dtype=np.float32,
                )

                file.write(
                    "World points (mm):\n"
                )

                file.write(
                    np.array2string(
                        world_points_mm,
                        precision=4,
                        suppress_small=True,
                    )
                )

                file.write(
                    "\n\n"
                )

            file.write(
                "Homography Matrix (H):\n"
            )

            file.write(
                np.array2string(
                    self.homography,
                    precision=10,
                    suppress_small=True,
                )
            )

            file.write(
                "\n\n"
            )

            if (
                self.reprojection_errors_mm
                is not None
            ):

                file.write(
                    "Reprojection Errors (mm):\n"
                )

                for index, error in enumerate(
                    self.reprojection_errors_mm
                ):

                    file.write(
                        f"Point {index}: "
                        f"{float(error):.8f} mm\n"
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