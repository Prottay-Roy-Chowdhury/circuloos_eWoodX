from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.workspace import (
    DirectoryManager,
)

from projects.ewoodx.config import (
    ARDUCAM_CALIBRATION_LAYOUT,
)


def main():

    with tempfile.TemporaryDirectory() as temp_dir:

        calibration_root = (
            Path(temp_dir)
            / "calibration_data"
        )

        directories = DirectoryManager(
            root=calibration_root,
            layout=ARDUCAM_CALIBRATION_LAYOUT,
        )

        print(
            "[test] Creating eWoodX "
            "calibration directories..."
        )

        directories.ensure_directories()

        for key in ARDUCAM_CALIBRATION_LAYOUT:

            path = directories.directory(
                key
            )

            assert path.exists()
            assert path.is_dir()

            print(
                f"[test] {key}: {path}"
            )

        intrinsic_file = (
            directories.directory(
                "intrinsic"
            )
            / "camera_intrinsics.npz"
        )

        extrinsic_file = (
            directories.directory(
                "extrinsic"
            )
            / "homography.npz"
        )

        print(
            "[test] Intrinsic file path:"
        )
        print(
            intrinsic_file
        )

        print(
            "[test] Extrinsic file path:"
        )
        print(
            extrinsic_file
        )

        assert (
            intrinsic_file.parent
            == directories.directory(
                "intrinsic"
            )
        )

        assert (
            extrinsic_file.parent
            == directories.directory(
                "extrinsic"
            )
        )

        print(
            "[test] eWoodX calibration "
            "directory test passed"
        )


if __name__ == "__main__":
    main()