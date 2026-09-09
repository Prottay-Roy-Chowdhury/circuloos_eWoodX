from pathlib import Path
import sys

import numpy as np


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from projects.ewoodx.operations.calibrate_arducam_extrinsic import (
    EWoodXArducamExtrinsicCalibration,
)


def main() -> None:

    print(
        "[test] Creating eWoodX Arducam "
        "extrinsic calibration operation..."
    )

    operation = (
        EWoodXArducamExtrinsicCalibration()
    )

    # -----------------------------------------------------
    # Synthetic detected ArUco markers
    # -----------------------------------------------------
    #
    # OpenCV ArUco corner order:
    #
    # 0 ---- 1
    # |      |
    # |      |
    # 3 ---- 2
    #
    # eWoodX configuration selects:
    #
    # marker 0 -> corner 0
    # marker 1 -> corner 1
    # marker 2 -> corner 2
    # marker 3 -> corner 3
    #
    # Selected pixel points therefore form:
    #
    # (100, 100) -------- (900, 100)
    #      |                    |
    #      |                    |
    # (100, 600) -------- (900, 600)
    #

    detected_markers = {
        0: np.array(
            [
                [100.0, 100.0],
                [200.0, 100.0],
                [200.0, 200.0],
                [100.0, 200.0],
            ],
            dtype=np.float32,
        ),

        1: np.array(
            [
                [800.0, 100.0],
                [900.0, 100.0],
                [900.0, 200.0],
                [800.0, 200.0],
            ],
            dtype=np.float32,
        ),

        2: np.array(
            [
                [800.0, 500.0],
                [900.0, 500.0],
                [900.0, 600.0],
                [800.0, 600.0],
            ],
            dtype=np.float32,
        ),

        3: np.array(
            [
                [100.0, 500.0],
                [200.0, 500.0],
                [200.0, 600.0],
                [100.0, 600.0],
            ],
            dtype=np.float32,
        ),
    }

    print(
        "[test] Building correspondences..."
    )

    (
        pixel_points,
        world_points_mm,
    ) = operation._build_correspondences(
        detected_markers
    )

    print(
        "[test] Pixel points:"
    )

    print(
        pixel_points
    )

    print(
        "[test] World points (mm):"
    )

    print(
        world_points_mm
    )

    # -----------------------------------------------------
    # Expected correspondences
    # -----------------------------------------------------

    expected_pixel_points = np.array(
        [
            [900.0, 100.0],  # marker 1, corner 1
            [100.0, 100.0],  # marker 0, corner 0
            [900.0, 600.0],  # marker 2, corner 2
            [100.0, 600.0],  # marker 3, corner 3
        ],
        dtype=np.float32,
    )

    expected_world_points_mm = np.array(
        [
            [0.0, 0.0],
            [776.0, 0.0],
            [0.0, 440.0],
            [776.0, 440.0],
        ],
        dtype=np.float32,
    )

    assert np.allclose(
        pixel_points,
        expected_pixel_points,
    ), (
        "Pixel correspondences do not match "
        "the configured eWoodX marker corners."
    )

    assert np.allclose(
        world_points_mm,
        expected_world_points_mm,
    ), (
        "World correspondences do not match "
        "the configured eWoodX coordinates."
    )

    print(
        "[test] Correspondence mapping passed"
    )

    # -----------------------------------------------------
    # Calculate homography using framework capability
    # -----------------------------------------------------

    print(
        "[test] Calculating homography..."
    )

    operation.extrinsic_calibration.calibrate(
        pixel_points=pixel_points,
        world_points_mm=world_points_mm,
    )

    homography = (
        operation
        .extrinsic_calibration
        .homography
    )

    print(
        "[test] Homography:"
    )

    print(
        homography
    )

    assert homography is not None

    # -----------------------------------------------------
    # Verify transformed calibration points
    # -----------------------------------------------------

    transformed_points = (
        operation
        .extrinsic_calibration
        .transform_points(
            pixel_points
        )
    )

    print(
        "[test] Transformed points:"
    )

    print(
        transformed_points
    )

    assert np.allclose(
        transformed_points,
        world_points_mm,
        atol=1e-3,
    ), (
        "Homography did not map the synthetic "
        "pixel points to the expected "
        "physical coordinates."
    )

    print(
        "[test] Homography mapping passed"
    )

    # -----------------------------------------------------
    # Reprojection error
    # -----------------------------------------------------

    errors = (
        operation
        .extrinsic_calibration
        .reprojection_errors_mm
    )

    print(
        "[test] Reprojection errors (mm):"
    )

    print(
        errors
    )

    assert errors is not None

    assert np.max(
        errors
    ) < 1e-3

    print(
        "[test] eWoodX Arducam extrinsic "
        "operation test passed"
    )


if __name__ == "__main__":
    main()