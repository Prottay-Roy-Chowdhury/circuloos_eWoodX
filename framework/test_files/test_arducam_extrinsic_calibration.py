from pathlib import Path
import sys
import tempfile

import numpy as np


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.sensing import (
    ArducamExtrinsicCalibration,
)


def main():

    print(
        "[test] Creating dummy extrinsic calibration..."
    )

    # -----------------------------------------------------
    # Known dummy pixel coordinates
    # -----------------------------------------------------

    pixel_points = np.array(
        [
            [100.0, 100.0],
            [900.0, 100.0],
            [100.0, 600.0],
            [900.0, 600.0],
        ],
        dtype=np.float32,
    )

    # -----------------------------------------------------
    # Known physical coordinates in millimetres
    # -----------------------------------------------------

    world_points_mm = np.array(
        [
            [0.0, 0.0],
            [800.0, 0.0],
            [0.0, 500.0],
            [800.0, 500.0],
        ],
        dtype=np.float32,
    )

    calibration = (
        ArducamExtrinsicCalibration()
    )

    assert not calibration.is_calibrated

    # -----------------------------------------------------
    # Calibrate
    # -----------------------------------------------------

    homography = calibration.calibrate(
        pixel_points=pixel_points,
        world_points_mm=world_points_mm,
    )

    assert calibration.is_calibrated
    assert homography.shape == (3, 3)

    print(
        "[test] Homography:"
    )
    print(
        homography
    )

    # -----------------------------------------------------
    # Verify calibration points
    # -----------------------------------------------------

    transformed = calibration.transform_points(
        pixel_points
    )

    print(
        "[test] Transformed calibration points:"
    )
    print(
        transformed
    )

    assert np.allclose(
        transformed,
        world_points_mm,
        atol=1e-4,
    )

    print(
        "[test] Reprojection errors (mm):"
    )
    print(
        calibration.reprojection_errors_mm
    )

    assert np.allclose(
        calibration.reprojection_errors_mm,
        0.0,
        atol=1e-4,
    )

    # -----------------------------------------------------
    # Test a point inside the calibrated region
    # -----------------------------------------------------

    test_pixel_point = np.array(
        [
            [500.0, 350.0],
        ],
        dtype=np.float32,
    )

    expected_world_point = np.array(
        [
            [400.0, 250.0],
        ],
        dtype=np.float32,
    )

    transformed_test_point = (
        calibration.transform_points(
            test_pixel_point
        )
    )

    print(
        "[test] Interior pixel point:"
    )
    print(
        test_pixel_point
    )

    print(
        "[test] Interior world point:"
    )
    print(
        transformed_test_point
    )

    assert np.allclose(
        transformed_test_point,
        expected_world_point,
        atol=1e-4,
    )

    # -----------------------------------------------------
    # Save and load
    # -----------------------------------------------------

    with tempfile.TemporaryDirectory() as temp_dir:

        calibration_file = (
            Path(temp_dir)
            / "homography.npz"
        )

        calibration.save(
            calibration_file
        )

        assert calibration_file.exists()

        print(
            "[test] Calibration saved:"
        )
        print(
            calibration_file
        )

        loaded = (
            ArducamExtrinsicCalibration.load(
                calibration_file
            )
        )

        assert loaded.is_calibrated

        loaded_result = (
            loaded.transform_points(
                test_pixel_point
            )
        )

        print(
            "[test] Loaded calibration result:"
        )
        print(
            loaded_result
        )

        assert np.allclose(
            loaded_result,
            expected_world_point,
            atol=1e-4,
        )

    print(
        "[test] Arducam extrinsic "
        "calibration test passed"
    )


if __name__ == "__main__":
    main()