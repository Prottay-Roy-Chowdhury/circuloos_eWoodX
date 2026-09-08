from pathlib import Path
import sys


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from framework.workspace import (
    init_workspace,
)


def main():

    layout = {
        "raw_images": (
            "sensing/raw/images"
        ),
        "point_clouds": (
            "sensing/raw/point_clouds"
        ),
        "processed": (
            "sensing/processed"
        ),
        "design_output": (
            "design/output"
        ),
        "robot_output": (
            "robot_control/output"
        ),
    }

    workspace = init_workspace(
        project_root=PROJECT_ROOT,
        workspace_name="wood_001",
        layout=layout,
    )

    print(
        "[test] Workspace created:"
    )
    print(workspace.root)

    for key in layout:
        print(
            f"[test] {key}: "
            f"{workspace.directory(key)}"
        )


if __name__ == "__main__":
    main()