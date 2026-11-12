"""
eWoodX - Projector Geometry

Geometry preparation, calibration, and coordinate
transformations for the eWoodX projector.

Responsibilities:
- Load calibrated projector homography.
- Prepare sensing measurements for projection.
- Accept complete Grasshopper geometry payloads.
- Convert world coordinates (mm) into projector pixels.
- Apply projector position and timber thickness compensation.
- Convert RGB/hex colors into OpenCV BGR colors.

Does not handle:
- TCP communication
- File monitoring
- Projection state
- OpenCV window management
- Rendering
"""

from __future__ import annotations

import copy
from pathlib import Path

import cv2
import numpy as np


class ProjectorGeometry:

    def __init__(
        self,
        homography: np.ndarray,
        projector_height_mm: float,
        projector_pos_x_mm: float,
        projector_pos_y_mm: float,
    ) -> None:

        self.homography = np.asarray(
            homography,
            dtype=np.float32,
        )

        if self.homography.shape != (3, 3):
            raise ValueError(
                "Homography must be a 3x3 matrix."
            )

        self.projector_height_mm = float(
            projector_height_mm
        )

        self.projector_pos_x_mm = float(
            projector_pos_x_mm
        )

        self.projector_pos_y_mm = float(
            projector_pos_y_mm
        )

    # -------------------------------------------------------------
    # Calibration loading
    # -------------------------------------------------------------

    @staticmethod
    def load_homography(
        homography_file: str | Path,
    ) -> np.ndarray:
        """
        Load the calibrated world-to-projector homography.

        Expected NPZ field:
            H_world_to_projector

        If the calibration file does not exist, return
        an identity homography for testing.

        Invalid or corrupted calibration files raise
        an exception rather than silently falling back.

        This preserves the existing projector behavior
        while centralizing calibration loading.
        """

        homography_file = Path(
            homography_file
        )

        if not homography_file.exists():

            print(
                "[Projector] Calibration not found:"
            )

            print(
                f"  {homography_file}"
            )

            print(
                "[Projector] Using identity homography "
                "for testing."
            )

            return np.eye(
                3,
                dtype=np.float32,
            )

        with np.load(
            homography_file,
            allow_pickle=True,
        ) as calibration:

            homography = np.asarray(
                calibration["H_world_to_projector"],
                dtype=np.float32,
            )

        if homography.shape != (3, 3):

            raise ValueError(
                "Calibration homography must be 3x3."
            )

        if not np.all(
            np.isfinite(homography)
        ):

            raise ValueError(
                "Calibration homography contains "
                "non-finite values."
            )

        print(
            "[Projector] Calibration loaded:"
        )

        print(
            f"  {homography_file}"
        )

        return homography

    # -------------------------------------------------------------
    # Alternative constructor
    # -------------------------------------------------------------

    @classmethod
    def from_calibration(
        cls,
        homography_file: str | Path,
        projector_height_mm: float,
        projector_pos_x_mm: float,
        projector_pos_y_mm: float,
    ) -> ProjectorGeometry:
        """
        Create ProjectorGeometry directly from
        a projector calibration NPZ file.

        The default constructor remains available
        for tests using an in-memory homography.
        """

        homography = cls.load_homography(
            homography_file
        )

        return cls(
            homography=homography,
            projector_height_mm=projector_height_mm,
            projector_pos_x_mm=projector_pos_x_mm,
            projector_pos_y_mm=projector_pos_y_mm,
        )

    # -------------------------------------------------------------
    # Sensing measurement preparation
    # -------------------------------------------------------------
    
    @staticmethod
    def prepare_measurement(measurement: dict) -> dict:
        """
        Convert legacy flat or capture-level sensing data
        into the renderer's existing flat geometry format.

        The original input is not modified.
        GH geometry is handled separately.
        """

        if not isinstance(measurement, dict):
            raise TypeError(
                "Measurement must be a dictionary."
            )

        data = copy.deepcopy(measurement)

        timbers = data.get("timbers")

        if timbers is not None:
            if not isinstance(timbers, list):
                raise ValueError(
                    "Measurement timbers must be a list."
                )

            contours = []
            corners = []
            holes = []
            defects = []

            for timber in timbers:
                if not isinstance(timber, dict):
                    raise ValueError(
                        "Each timber must be a dictionary."
                    )

                contour = timber.get("contour_mm") or []
                if len(contour) >= 3:
                    contours.append(contour)

                timber_corners = timber.get("corners_mm") or []
                if len(timber_corners) >= 3:
                    corners.append(timber_corners)

                for hole in timber.get("holes_mm") or []:
                    if len(hole) >= 3:
                        holes.append(hole)

                defects.extend(timber.get("defects") or [])

            data["contour_mm"] = contours
            data["corners_mm"] = corners
            data["holes_mm"] = holes
            data["defects"] = defects

            if timbers:
                first = timbers[0]

                data["length_mm"] = first.get(
                    "length_mm", 0.0
                )
                data["width_mm"] = first.get(
                    "width_mm", 0.0
                )

                if data.get("thickness_mm") is None:
                    data["thickness_mm"] = first.get(
                        "timber_thickness_mm",
                        first.get("thickness_mm", 0.0),
                    )

        else:
            # Legacy flat measurement.
            if data.get("thickness_mm") is None:
                data["thickness_mm"] = data.get(
                    "timber_thickness_mm", 0.0
                )

            data.setdefault("holes_mm", [])

        data.setdefault("contour_mm", [])
        data.setdefault("corners_mm", [])
        data.setdefault("defects", [])
        data.setdefault("cut_geo", [])
        data.setdefault("mill_geo", [])
        data.setdefault("points_geo", [])
        data.setdefault("labels", [])

        return data

    # -------------------------------------------------------------
    # Grasshopper geometry preparation
    # -------------------------------------------------------------

    @staticmethod
    def prepare_gh_geometry(
        geometry: dict,
    ) -> dict:
        """
        Prepare a complete Grasshopper geometry payload.

        GH already reads the timber measurement and adds its
        design geometry.

        Therefore, the received payload is not merged with
        the current sensing measurement.
        """

        if not isinstance(
            geometry,
            dict,
        ):

            raise TypeError(
                "Grasshopper geometry must be a dictionary."
            )

        return copy.deepcopy(
            geometry
        )

    # -------------------------------------------------------------
    # World coordinates -> projector pixels
    # -------------------------------------------------------------

    def world_to_projector(
        self,
        points_mm,
        off_x: float = 0.0,
        off_y: float = 0.0,
        thickness_mm: float = 0.0,
    ) -> np.ndarray:
        """
        Transform world XY coordinates in millimeters into
        calibrated projector pixel coordinates.

        Preserves the transformation order of the existing
        projector_live_viewer.py:

        1. Apply XY offsets.
        2. Apply timber thickness/parallax compensation.
        3. Apply calibrated homography.
        """

        if (
            points_mm is None
            or len(points_mm) == 0
        ):

            return np.empty(
                (0, 2),
                dtype=np.float32,
            )

        points = np.asarray(
            points_mm,
            dtype=np.float32,
        ).copy()

        if (
            points.ndim == 1
            and len(points) == 2
        ):

            points = points.reshape(
                1, 2
            )

        # ---------------------------------------------------------
        # XY offsets
        # ---------------------------------------------------------

        points[:, 0] += off_x
        points[:, 1] += off_y

        # ---------------------------------------------------------
        # Parallax compensation
        # ---------------------------------------------------------

        if (
            thickness_mm > 0.0
            and self.projector_height_mm > thickness_mm
        ):

            scale_factor = (
                self.projector_height_mm
                / (
                    self.projector_height_mm
                    - thickness_mm
                )
            )

            points[:, 0] = (
                self.projector_pos_x_mm
                + (
                    points[:, 0]
                    - self.projector_pos_x_mm
                )
                * scale_factor
            )

            points[:, 1] = (
                self.projector_pos_y_mm
                + (
                    points[:, 1]
                    - self.projector_pos_y_mm
                )
                * scale_factor
            )

        # ---------------------------------------------------------
        # Homography transformation
        # ---------------------------------------------------------

        projected = cv2.perspectiveTransform(
            points.reshape(-1, 1, 2),
            self.homography,
        )

        return projected.reshape(
            -1,
            2,
        )

    # -------------------------------------------------------------
    # Color conversion
    # -------------------------------------------------------------

    @staticmethod
    def parse_color(
        color_val,
        default_bgr=(255, 255, 255),
    ):
        """
        Convert supported color representations to OpenCV BGR.

        Supported:
        - Hex string: "#FF0000"
        - RGB list/tuple: [255, 0, 0]
        - RGB dictionary: {"R": 255, "G": 0, "B": 0}

        Preserves the existing viewer's color conversion.
        """

        if color_val is None:

            return default_bgr

        try:

            if isinstance(
                color_val,
                str,
            ):

                color_string = (
                    color_val.strip().lstrip("#")
                )

                if len(
                    color_string
                ) in (6, 8):

                    red = int(
                        color_string[0:2],
                        16,
                    )

                    green = int(
                        color_string[2:4],
                        16,
                    )

                    blue = int(
                        color_string[4:6],
                        16,
                    )

                    return (
                        blue,
                        green,
                        red,
                    )

            elif isinstance(
                color_val,
                (list, tuple),
            ):

                if len(
                    color_val
                ) >= 3:

                    red = int(
                        color_val[0]
                    )

                    green = int(
                        color_val[1]
                    )

                    blue = int(
                        color_val[2]
                    )

                    return (
                        blue,
                        green,
                        red,
                    )

            elif isinstance(
                color_val,
                dict,
            ):

                red = int(
                    color_val.get(
                        "R",
                        color_val.get(
                            "r",
                            255,
                        ),
                    )
                )

                green = int(
                    color_val.get(
                        "G",
                        color_val.get(
                            "g",
                            255,
                        ),
                    )
                )

                blue = int(
                    color_val.get(
                        "B",
                        color_val.get(
                            "b",
                            255,
                        ),
                    )
                )

                return (
                    blue,
                    green,
                    red,
                )

        except Exception:

            pass

        return default_bgr