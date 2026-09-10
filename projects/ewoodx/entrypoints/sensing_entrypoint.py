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


def run_sensing(
    workspace: WorkspacePaths | None = None,
) -> None:
    """
    Start the eWoodX sensing process.

    A workspace may be supplied programmatically
    later by orchestration. If none is supplied,
    interactive workspace selection is used.
    """

    if workspace is None:

        workspace = (
            resolve_workspace()
        )

    print()
    print(
        "[eWoodX] Active workspace:"
    )

    print(
        workspace.root
    )

    operation = (
        EWoodXTimberSegmentationArducam(
            workspace=workspace
        )
    )

    operation.run()


def main(
) -> None:

    run_sensing()


if __name__ == "__main__":
    main()