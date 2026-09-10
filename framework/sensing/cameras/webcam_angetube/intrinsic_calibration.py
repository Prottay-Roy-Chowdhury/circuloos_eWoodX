"""
Intrinsic calibration for the Angetube webcam setup.
"""

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


class AngetubeIntrinsicCalibration:
    """
    Intrinsic camera calibration for the Angetube webcam.

    Supports:

    - standard pinhole calibration
    - OpenCV fisheye calibration
    - checkerboard corner detection
    - storing calibration results
    - saving / loading calibration data
    - cached image undistortion
    """

    def __init__(
        self,
        checkerboard_inner_corners: tuple[int, int],
        square_size_mm: float,
        calibration_model: str = "fisheye",
        fisheye_balance: float = 0.0,
        fisheye_fov_scale: float = 1.0,
        fisheye_check_cond: bool = True,
        fisheye_recompute_extrinsic: bool = True,
        fisheye_fix_skew: bool = True,
    ) -> None:

        cols, rows = (
            checkerboard_inner_corners
        )

        if cols <= 0 or rows <= 0:

            raise ValueError(
                "checkerboard_inner_corners "
                "must contain positive values."
            )

        if square_size_mm <= 0:

            raise ValueError(
                "square_size_mm must be "
                "greater than zero."
            )

        calibration_model = (
            calibration_model
            .strip()
            .lower()
        )

        if calibration_model not in (
            "standard",
            "fisheye",
        ):

            raise ValueError(
                "calibration_model must be "
                "'standard' or 'fisheye'."
            )

        if not (
            0.0
            <= fisheye_balance
            <= 1.0
        ):

            raise ValueError(
                "fisheye_balance must be "
                "between 0.0 and 1.0."
            )

        if fisheye_fov_scale <= 0:

            raise ValueError(
                "fisheye_fov_scale must be "
                "greater than zero."
            )

        self.checkerboard_inner_corners = (
            int(cols),
            int(rows),
        )

        self.square_size_mm = float(
            square_size_mm
        )

        self.calibration_model = (
            calibration_model
        )

        self.fisheye_balance = float(
            fisheye_balance
        )

        self.fisheye_fov_scale = float(
            fisheye_fov_scale
        )

        self.fisheye_check_cond = bool(
            fisheye_check_cond
        )

        self.fisheye_recompute_extrinsic = bool(
            fisheye_recompute_extrinsic
        )

        self.fisheye_fix_skew = bool(
            fisheye_fix_skew
        )

        self.camera_matrix: (
            np.ndarray
            | None
        ) = None

        self.dist_coeffs: (
            np.ndarray
            | None
        ) = None

        self.image_size: (
            tuple[int, int]
            | None
        ) = None

        self.rms_error: (
            float
            | None
        ) = None

        self.accepted_images = 0
        self.total_images = 0

        self._cached_maps = {}

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------

    @property
    def is_calibrated(
        self,
    ) -> bool:

        return (
            self.camera_matrix
            is not None

            and self.dist_coeffs
            is not None

            and self.image_size
            is not None

            and self.rms_error
            is not None
        )

    @property
    def is_fisheye(
        self,
    ) -> bool:

        return (
            self.calibration_model
            == "fisheye"
        )

    # -----------------------------------------------------------------
    # Calibration
    # -----------------------------------------------------------------

    def calibrate(
        self,
        image_paths: Iterable[
            str | Path
        ],
    ) -> None:
        """
        Calibrate the camera using
        checkerboard images.
        """

        paths = [
            Path(path)
            for path in image_paths
        ]

        if not paths:

            raise ValueError(
                "No calibration images provided."
            )

        if self.is_fisheye:

            (
                object_points_template,
                object_points,
                image_points,
            ) = (
                self._prepare_fisheye_points()
            )

        else:

            (
                object_points_template,
                object_points,
                image_points,
            ) = (
                self._prepare_standard_points()
            )

        cols, rows = (
            self.checkerboard_inner_corners
        )

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

            elif (
                current_image_size
                != image_size
            ):

                raise ValueError(
                    "All calibration images must "
                    "have the same resolution."
                )

            found, corners = (
                cv2.findChessboardCorners(
                    gray,
                    (
                        cols,
                        rows,
                    ),
                    (
                        cv2.CALIB_CB_ADAPTIVE_THRESH
                        + cv2.CALIB_CB_FAST_CHECK
                        + cv2.CALIB_CB_NORMALIZE_IMAGE
                    ),
                )
            )

            if not found:
                continue

            corners_refined = (
                cv2.cornerSubPix(
                    gray,
                    corners,
                    (
                        11,
                        11,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    criteria,
                )
            )

            if self.is_fisheye:

                object_points.append(
                    object_points_template.copy()
                )

                image_points.append(
                    np.asarray(
                        corners_refined,
                        dtype=np.float64,
                    ).reshape(
                        1,
                        -1,
                        2,
                    )
                )

            else:

                object_points.append(
                    object_points_template.copy()
                )

                image_points.append(
                    corners_refined
                )

            accepted += 1

        self.total_images = (
            len(paths)
        )

        self.accepted_images = (
            accepted
        )

        if accepted == 0:

            raise RuntimeError(
                "Checkerboard could not be "
                "detected in any calibration image."
            )

        if image_size is None:

            raise RuntimeError(
                "Calibration image size "
                "could not be determined."
            )

        if self.is_fisheye:

            (
                rms_error,
                camera_matrix,
                dist_coeffs,
            ) = (
                self._calibrate_fisheye(
                    object_points=(
                        object_points
                    ),
                    image_points=(
                        image_points
                    ),
                    image_size=(
                        image_size
                    ),
                )
            )

        else:

            (
                rms_error,
                camera_matrix,
                dist_coeffs,
            ) = (
                self._calibrate_standard(
                    object_points=(
                        object_points
                    ),
                    image_points=(
                        image_points
                    ),
                    image_size=(
                        image_size
                    ),
                )
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

        self._cached_maps.clear()

    # -----------------------------------------------------------------
    # Point preparation
    # -----------------------------------------------------------------

    def _prepare_standard_points(
        self,
    ):

        cols, rows = (
            self.checkerboard_inner_corners
        )

        object_points_template = (
            np.zeros(
                (
                    cols * rows,
                    3,
                ),
                dtype=np.float32,
            )
        )

        object_points_template[
            :,
            :2,
        ] = (
            np.mgrid[
                0:cols,
                0:rows,
            ]
            .T
            .reshape(
                -1,
                2,
            )
            * self.square_size_mm
        )

        return (
            object_points_template,
            [],
            [],
        )

    def _prepare_fisheye_points(
        self,
    ):

        cols, rows = (
            self.checkerboard_inner_corners
        )

        object_points_template = (
            np.zeros(
                (
                    1,
                    cols * rows,
                    3,
                ),
                dtype=np.float64,
            )
        )

        object_points_template[
            0,
            :,
            :2,
        ] = (
            np.mgrid[
                0:cols,
                0:rows,
            ]
            .T
            .reshape(
                -1,
                2,
            )
            * self.square_size_mm
        )

        return (
            object_points_template,
            [],
            [],
        )

    # -----------------------------------------------------------------
    # Standard calibration
    # -----------------------------------------------------------------

    @staticmethod
    def _calibrate_standard(
        object_points,
        image_points,
        image_size,
    ):

        (
            rms_error,
            camera_matrix,
            dist_coeffs,
            _,
            _,
        ) = (
            cv2.calibrateCamera(
                object_points,
                image_points,
                image_size,
                None,
                None,
            )
        )

        return (
            rms_error,
            camera_matrix,
            dist_coeffs,
        )

    # -----------------------------------------------------------------
    # Fisheye calibration
    # -----------------------------------------------------------------

    def _calibrate_fisheye(
        self,
        object_points,
        image_points,
        image_size,
    ):

        camera_matrix = (
            np.zeros(
                (
                    3,
                    3,
                ),
                dtype=np.float64,
            )
        )

        dist_coeffs = (
            np.zeros(
                (
                    4,
                    1,
                ),
                dtype=np.float64,
            )
        )

        calibration_flags = 0

        flag_check_cond = getattr(
            cv2.fisheye,
            "CALIB_CHECK_COND",
            4,
        )

        flag_recompute_extrinsic = getattr(
            cv2.fisheye,
            "CALIB_RECOMPUTE_EXTRINSIC",
            2,
        )

        flag_fix_skew = getattr(
            cv2.fisheye,
            "CALIB_FIX_SKEW",
            8,
        )

        if self.fisheye_check_cond:

            calibration_flags |= (
                flag_check_cond
            )

        if self.fisheye_recompute_extrinsic:

            calibration_flags |= (
                flag_recompute_extrinsic
            )

        if self.fisheye_fix_skew:

            calibration_flags |= (
                flag_fix_skew
            )

        criteria = (
            cv2.TERM_CRITERIA_EPS
            + cv2.TERM_CRITERIA_MAX_ITER,
            100,
            1e-6,
        )

        try:

            (
                rms_error,
                camera_matrix,
                dist_coeffs,
                _,
                _,
            ) = (
                cv2.fisheye.calibrate(
                    object_points,
                    image_points,
                    image_size,
                    camera_matrix,
                    dist_coeffs,
                    None,
                    None,
                    calibration_flags,
                    criteria,
                )
            )

        except cv2.error:

            if (
                self.fisheye_check_cond
            ):

                calibration_flags &= (
                    ~flag_check_cond
                )

                (
                    rms_error,
                    camera_matrix,
                    dist_coeffs,
                    _,
                    _,
                ) = (
                    cv2.fisheye.calibrate(
                        object_points,
                        image_points,
                        image_size,
                        camera_matrix,
                        dist_coeffs,
                        None,
                        None,
                        calibration_flags,
                        criteria,
                    )
                )

            else:

                raise

        return (
            rms_error,
            camera_matrix,
            dist_coeffs,
        )

    # -----------------------------------------------------------------
    # Undistortion
    # -----------------------------------------------------------------

    def undistort(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """
        Return an undistorted image.

        Undistortion maps are cached per
        image resolution.
        """

        if not self.is_calibrated:

            raise RuntimeError(
                "Camera calibration "
                "is not available."
            )

        if image is None:

            raise ValueError(
                "image cannot be None."
            )

        image = np.asarray(
            image
        )

        if image.ndim not in (
            2,
            3,
        ):

            raise ValueError(
                "image must be grayscale "
                "or BGR."
            )

        height, width = (
            image.shape[:2]
        )

        map1, map2, _ = (
            self._get_undistortion_maps(
                image_size=(
                    width,
                    height,
                )
            )
        )

        return (
            cv2.remap(
                image,
                map1,
                map2,
                interpolation=(
                    cv2.INTER_LINEAR
                ),
                borderMode=(
                    cv2.BORDER_CONSTANT
                ),
            )
        )

    def _get_undistortion_maps(
        self,
        image_size: tuple[
            int,
            int,
        ],
    ):

        if not self.is_calibrated:

            raise RuntimeError(
                "Camera calibration "
                "is not available."
            )

        width, height = (
            image_size
        )

        cache_key = (
            width,
            height,
            self.calibration_model,
            self.fisheye_balance,
            self.fisheye_fov_scale,
        )

        if cache_key in (
            self._cached_maps
        ):

            return (
                self._cached_maps[
                    cache_key
                ]
            )

        camera_matrix = (
            self._scaled_camera_matrix(
                image_size
            )
        )

        if self.is_fisheye:

            dist_coeffs = (
                np.asarray(
                    self.dist_coeffs,
                    dtype=np.float64,
                )
                .reshape(
                    4,
                    1,
                )
            )

            new_camera_matrix = (
                cv2.fisheye
                .estimateNewCameraMatrixForUndistortRectify(
                    camera_matrix,
                    dist_coeffs,
                    image_size,
                    np.eye(
                        3,
                        dtype=np.float64,
                    ),
                    balance=(
                        self.fisheye_balance
                    ),
                    new_size=(
                        image_size
                    ),
                    fov_scale=(
                        self.fisheye_fov_scale
                    ),
                )
            )

            map1, map2 = (
                cv2.fisheye
                .initUndistortRectifyMap(
                    camera_matrix,
                    dist_coeffs,
                    np.eye(
                        3,
                        dtype=np.float64,
                    ),
                    new_camera_matrix,
                    image_size,
                    cv2.CV_16SC2,
                )
            )

        else:

            (
                new_camera_matrix,
                _,
            ) = (
                cv2.getOptimalNewCameraMatrix(
                    camera_matrix,
                    self.dist_coeffs,
                    image_size,
                    alpha=(
                        self.fisheye_balance
                    ),
                    newImgSize=(
                        image_size
                    ),
                )
            )

            map1, map2 = (
                cv2.initUndistortRectifyMap(
                    camera_matrix,
                    self.dist_coeffs,
                    None,
                    new_camera_matrix,
                    image_size,
                    cv2.CV_16SC2,
                )
            )

        result = (
            map1,
            map2,
            new_camera_matrix,
        )

        self._cached_maps[
            cache_key
        ] = result

        return result

    # -----------------------------------------------------------------
    # Camera matrix scaling
    # -----------------------------------------------------------------

    def _scaled_camera_matrix(
        self,
        image_size: tuple[
            int,
            int,
        ],
    ) -> np.ndarray:

        if not self.is_calibrated:

            raise RuntimeError(
                "Camera calibration "
                "is not available."
            )

        current_width, current_height = (
            image_size
        )

        calibration_width, calibration_height = (
            self.image_size
        )

        scaled_matrix = (
            np.asarray(
                self.camera_matrix,
                dtype=np.float64,
            ).copy()
        )

        if (
            current_width
            == calibration_width

            and current_height
            == calibration_height
        ):

            return scaled_matrix

        scale_x = (
            current_width
            / float(
                calibration_width
            )
        )

        scale_y = (
            current_height
            / float(
                calibration_height
            )
        )

        scaled_matrix[
            0,
            0,
        ] *= scale_x

        scaled_matrix[
            0,
            2,
        ] *= scale_x

        scaled_matrix[
            1,
            1,
        ] *= scale_y

        scaled_matrix[
            1,
            2,
        ] *= scale_y

        return scaled_matrix

    # -----------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------

    def save(
        self,
        file_path: str | Path,
    ) -> None:
        """
        Save intrinsic calibration data
        to an NPZ file.
        """

        if not self.is_calibrated:

            raise RuntimeError(
                "Camera calibration "
                "is not available."
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
            camera_matrix=(
                self.camera_matrix
            ),
            dist_coeffs=(
                self.dist_coeffs
            ),
            image_size=(
                np.asarray(
                    self.image_size,
                    dtype=np.int32,
                )
            ),
            rms_error=(
                self.rms_error
            ),
            accepted_images=(
                self.accepted_images
            ),
            total_images=(
                self.total_images
            ),
            calibration_model=(
                self.calibration_model
            ),
            is_fisheye=(
                self.is_fisheye
            ),
            fisheye_balance=(
                self.fisheye_balance
            ),
            fisheye_fov_scale=(
                self.fisheye_fov_scale
            ),
            fisheye_check_cond=(
                self.fisheye_check_cond
            ),
            fisheye_recompute_extrinsic=(
                self.fisheye_recompute_extrinsic
            ),
            fisheye_fix_skew=(
                self.fisheye_fix_skew
            ),
            checkerboard_inner_corners=(
                np.asarray(
                    self.checkerboard_inner_corners,
                    dtype=np.int32,
                )
            ),
            square_size_mm=(
                self.square_size_mm
            ),
        )

    # -----------------------------------------------------------------
    # Load
    # -----------------------------------------------------------------

    @classmethod
    def load(
        cls,
        file_path: str | Path,
    ) -> "AngetubeIntrinsicCalibration":
        """
        Load intrinsic calibration
        from an NPZ file.
        """

        path = Path(
            file_path
        )

        if not path.exists():

            raise FileNotFoundError(
                "Calibration file "
                f"not found: {path}"
            )

        data = np.load(
            path,
            allow_pickle=False,
        )

        if (
            "calibration_model"
            in data
        ):

            calibration_model = str(
                data[
                    "calibration_model"
                ].item()
            )

        elif (
            "is_fisheye"
            in data
        ):

            calibration_model = (
                "fisheye"
                if bool(
                    data[
                        "is_fisheye"
                    ].item()
                )
                else "standard"
            )

        else:

            calibration_model = (
                "standard"
            )

        if (
            "checkerboard_inner_corners"
            in data
        ):

            corners = (
                data[
                    "checkerboard_inner_corners"
                ]
                .astype(
                    int
                )
                .tolist()
            )

            checkerboard_inner_corners = (
                int(
                    corners[0]
                ),
                int(
                    corners[1]
                ),
            )

        else:

            checkerboard_inner_corners = (
                1,
                1,
            )

        if (
            "square_size_mm"
            in data
        ):

            square_size_mm = float(
                data[
                    "square_size_mm"
                ].item()
            )

        else:

            square_size_mm = 1.0

        instance = cls(
            checkerboard_inner_corners=(
                checkerboard_inner_corners
            ),
            square_size_mm=(
                square_size_mm
            ),
            calibration_model=(
                calibration_model
            ),
            fisheye_balance=(
                float(
                    data[
                        "fisheye_balance"
                    ].item()
                )
                if (
                    "fisheye_balance"
                    in data
                )
                else 0.0
            ),
            fisheye_fov_scale=(
                float(
                    data[
                        "fisheye_fov_scale"
                    ].item()
                )
                if (
                    "fisheye_fov_scale"
                    in data
                )
                else 1.0
            ),
            fisheye_check_cond=(
                bool(
                    data[
                        "fisheye_check_cond"
                    ].item()
                )
                if (
                    "fisheye_check_cond"
                    in data
                )
                else True
            ),
            fisheye_recompute_extrinsic=(
                bool(
                    data[
                        "fisheye_recompute_extrinsic"
                    ].item()
                )
                if (
                    "fisheye_recompute_extrinsic"
                    in data
                )
                else True
            ),
            fisheye_fix_skew=(
                bool(
                    data[
                        "fisheye_fix_skew"
                    ].item()
                )
                if (
                    "fisheye_fix_skew"
                    in data
                )
                else True
            ),
        )

        instance.camera_matrix = (
            np.asarray(
                data[
                    "camera_matrix"
                ],
                dtype=np.float64,
            )
        )

        instance.dist_coeffs = (
            np.asarray(
                data[
                    "dist_coeffs"
                ],
                dtype=np.float64,
            )
        )

        image_size = (
            data[
                "image_size"
            ]
            .astype(
                int
            )
            .tolist()
        )

        instance.image_size = (
            int(
                image_size[0]
            ),
            int(
                image_size[1]
            ),
        )

        instance.rms_error = float(
            data[
                "rms_error"
            ].item()
        )

        if (
            "accepted_images"
            in data
        ):

            instance.accepted_images = int(
                data[
                    "accepted_images"
                ].item()
            )

        if (
            "total_images"
            in data
        ):

            instance.total_images = int(
                data[
                    "total_images"
                ].item()
            )

        instance._cached_maps.clear()

        return instance