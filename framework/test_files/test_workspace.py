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
    init_workspace,
    load_workspace,
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

    with tempfile.TemporaryDirectory() as temp_dir:

        project_root = Path(
            temp_dir
        )

        print(
            "[test] Creating workspace..."
        )

        workspace = init_workspace(
            project_root=project_root,
            workspace_name="wood_001",
            layout=layout,
        )

        assert workspace.root.exists()
        assert workspace.manifest.exists()

        for key in layout:

            path = workspace.directory(
                key
            )

            assert path.exists()
            assert path.is_dir()

            print(
                f"[test] {key}: {path}"
            )

        print(
            "[test] Loading workspace "
            "by name..."
        )

        loaded = load_workspace(
            project_root=project_root,
            workspace_name="wood_001",
        )

        assert (
            loaded.workspace_name
            == "wood_001"
        )

        assert (
            loaded.directory(
                "raw_images"
            )
            == workspace.directory(
                "raw_images"
            )
        )

        print(
            "[test] Loading most recent "
            "workspace..."
        )

        recent = load_workspace(
            project_root=project_root,
        )

        assert (
            recent.workspace_name
            == "wood_001"
        )

        print(
            "[test] Creating second "
            "workspace..."
        )

        second = init_workspace(
            project_root=project_root,
            workspace_name="wood_002",
            layout=layout,
        )

        latest = load_workspace(
            project_root=project_root,
        )

        assert (
            latest.workspace_name
            == "wood_002"
        )

        assert (
            latest.root
            == second.root
        )

        print(
            "[test] Workspace test passed"
        )


if __name__ == "__main__":
    main()