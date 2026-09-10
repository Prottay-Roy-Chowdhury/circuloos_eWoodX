from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.workspace import (
    WorkspacePaths,
    init_workspace,
    load_workspace,
)

from projects.ewoodx.config import (
    EWOODX_PROJECT_ROOT,
    EWOODX_SENSING_WORKSPACE_LAYOUT,
)

from projects.ewoodx.operations.timber_segmentation_arducam import (
    EWoodXTimberSegmentationArducam,
)

from projects.ewoodx.operations.timber_segmentation_angetube import (
    EWoodXTimberSegmentationAngetube,
)


def resolve_workspace(
) -> WorkspacePaths:
    """
    Interactively choose the workspace used
    by the current eWoodX sensing process.
    """

    while True:

        print()
        print(
            "eWoodX Sensing"
        )

        print(
            "=============="
        )

        print()
        print(
            "Workspace:"
        )

        print(
            "[1] Use last workspace"
        )

        print(
            "[2] Open workspace by name"
        )

        print(
            "[3] Create new workspace"
        )

        print(
            "[4] Exit"
        )

        choice = (
            input(
                "Select: "
            )
            .strip()
        )

        if choice == "1":

            try:

                workspace = (
                    load_workspace(
                        project_root=(
                            EWOODX_PROJECT_ROOT
                        )
                    )
                )

                return workspace

            except FileNotFoundError as error:

                print()
                print(
                    f"[eWoodX] {error}"
                )

        elif choice == "2":

            workspace_name = (
                input(
                    "Workspace name: "
                )
                .strip()
            )

            if not workspace_name:

                print(
                    "[eWoodX] Workspace "
                    "name cannot be empty."
                )

                continue

            try:

                workspace = (
                    load_workspace(
                        project_root=(
                            EWOODX_PROJECT_ROOT
                        ),
                        workspace_name=(
                            workspace_name
                        ),
                    )
                )

                return workspace

            except FileNotFoundError as error:

                print()
                print(
                    f"[eWoodX] {error}"
                )

        elif choice == "3":

            workspace_name = (
                input(
                    "New workspace name: "
                )
                .strip()
            )

            if not workspace_name:

                print(
                    "[eWoodX] Workspace "
                    "name cannot be empty."
                )

                continue

            workspace_path = (
                EWOODX_PROJECT_ROOT
                / "workspaces"
                / workspace_name
            )

            if workspace_path.exists():

                print(
                    "[eWoodX] Workspace already "
                    f"exists: {workspace_name}"
                )

                print(
                    "[eWoodX] Use option 2 "
                    "to open it."
                )

                continue

            workspace = (
                init_workspace(
                    project_root=(
                        EWOODX_PROJECT_ROOT
                    ),
                    workspace_name=(
                        workspace_name
                    ),
                    layout=(
                        EWOODX_SENSING_WORKSPACE_LAYOUT
                    ),
                )
            )

            return workspace

        elif choice == "4":

            raise SystemExit(
                0
            )

        else:

            print(
                "[eWoodX] Invalid selection."
            )


def resolve_sensing_equipment(
) -> str:
    """
    Interactively choose which sensing equipment
    is used for the current sensing process.
    """

    while True:

        print()
        print(
            "Sensing equipment:"
        )

        print(
            "[1] Arducam"
        )

        print(
            "[2] Webcam"
        )

        print(
            "[3] Exit"
        )

        choice = (
            input(
                "Select: "
            )
            .strip()
        )

        if choice == "1":

            return "arducam"

        elif choice == "2":

            return "webcam"

        elif choice == "3":

            raise SystemExit(
                0
            )

        else:

            print(
                "[eWoodX] Invalid selection."
            )


def run_sensing(
    workspace: WorkspacePaths | None = None,
    equipment: str | None = None,
) -> None:
    """
    Start the eWoodX sensing process.

    Workspace and sensing equipment may be
    supplied programmatically later by
    orchestration.

    If either is not supplied, the corresponding
    interactive selection is used.
    """

    if workspace is None:

        workspace = (
            resolve_workspace()
        )

    if equipment is None:

        equipment = (
            resolve_sensing_equipment()
        )

    equipment = (
        equipment
        .strip()
        .lower()
    )

    print()
    print(
        "[eWoodX] Active workspace:"
    )

    print(
        workspace.root
    )

    print(
        "[eWoodX] Sensing equipment:"
    )

    print(
        equipment
    )

    if equipment == "arducam":

        operation = (
            EWoodXTimberSegmentationArducam(
                workspace=workspace
            )
        )

    elif equipment == "webcam":

        operation = (
            EWoodXTimberSegmentationAngetube(
                workspace=workspace
            )
        )

    else:

        raise ValueError(
            "Unknown sensing equipment: "
            f"{equipment}"
        )

    operation.run()


def main(
) -> None:

    run_sensing()


if __name__ == "__main__":
    main()