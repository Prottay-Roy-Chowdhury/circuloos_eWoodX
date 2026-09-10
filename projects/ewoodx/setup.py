from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.workspace import DirectoryManager

from projects.ewoodx.config import (
    CALIBRATION_ROOT,
    ARDUCAM_CALIBRATION_LAYOUT,
    ANGETUBE_CALIBRATION_LAYOUT,
)


def setup_ewoodx_project() -> None:
    """
    Prepare persistent project-level directories required by eWoodX.

    Runtime workspaces are intentionally not created here.
    They should be created separately when a new batch/run starts.
    """

    print(
        "[eWoodX] Setting up persistent project directories..."
    )

    # -----------------------------------------------------------------
    # Arducam calibration directories
    # -----------------------------------------------------------------

    arducam_calibration_directories = DirectoryManager(
        root=CALIBRATION_ROOT,
        layout=ARDUCAM_CALIBRATION_LAYOUT,
    )

    arducam_calibration_directories.ensure_directories()

    print(
        "[eWoodX] Arducam calibration directories:"
    )

    for key, path in (
        arducam_calibration_directories
        .directories()
        .items()
    ):
        print(
            f"[eWoodX] {key}: {path}"
        )

    # -----------------------------------------------------------------
    # Angetube calibration directories
    # -----------------------------------------------------------------

    angetube_calibration_directories = DirectoryManager(
        root=CALIBRATION_ROOT,
        layout=ANGETUBE_CALIBRATION_LAYOUT,
    )

    angetube_calibration_directories.ensure_directories()

    print(
        "[eWoodX] Angetube calibration directories:"
    )

    for key, path in (
        angetube_calibration_directories
        .directories()
        .items()
    ):
        print(
            f"[eWoodX] {key}: {path}"
        )

    print(
        "[eWoodX] Project setup complete."
    )


if __name__ == "__main__":
    setup_ewoodx_project()