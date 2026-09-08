"""Generic project workspace management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import platform
from typing import Dict

from framework.workspace.directory_manager import (
    DirectoryManager,
)


WORKSPACES_DIR = "workspaces"
MANIFEST_FILE = "workspace.json"
RECENT_FILE = ".last_workspace"
LATEST_POINTER = "latest"


@dataclass
class WorkspacePaths:
    """
    Paths belonging to one project workspace.
    """

    root: Path
    workspace_name: str
    directories: Dict[str, Path]
    manifest: Path

    def directory(
        self,
        key: str,
    ) -> Path:
        """
        Return a configured workspace directory.
        """

        if key not in self.directories:
            raise KeyError(
                f"Unknown workspace directory: {key}"
            )

        return self.directories[key]


def _workspaces_dir(
    project_root: Path,
) -> Path:
    return (
        project_root
        / WORKSPACES_DIR
    ).resolve()


def _safe_latest_pointer(
    parent: Path,
    workspace_dir: Path,
) -> None:
    """
    Create a 'latest' workspace pointer.

    Uses a relative symlink when supported.
    Falls back to a text file otherwise.
    """

    latest = parent / LATEST_POINTER

    try:

        if (
            latest.exists()
            or latest.is_symlink()
        ):
            latest.unlink()

        latest.symlink_to(
            workspace_dir.name,
            target_is_directory=True,
        )

    except Exception:

        latest.write_text(
            str(workspace_dir.resolve()),
            encoding="utf-8",
        )


def _write_manifest(
    workspace_name: str,
    workspace_dir: Path,
    directory_manager: DirectoryManager,
) -> Path:

    manifest = (
        workspace_dir
        / MANIFEST_FILE
    )

    data = {
        "workspace_name": workspace_name,
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "directories": (
            directory_manager
            .relative_layout()
        ),
        "platform": platform.platform(),
    }

    manifest.write_text(
        json.dumps(
            data,
            indent=2,
        ),
        encoding="utf-8",
    )

    return manifest


def init_workspace(
    project_root: str | Path,
    workspace_name: str,
    layout: Dict[str, str | Path],
) -> WorkspacePaths:
    """
    Create or initialize a named project workspace.

    Directory structure is supplied by the project.
    """

    if not isinstance(
        workspace_name,
        str,
    ):
        raise TypeError(
            "workspace_name must be a string."
        )

    workspace_name = (
        workspace_name.strip()
    )

    if not workspace_name:
        raise ValueError(
            "workspace_name cannot be empty."
        )

    project_root = Path(
        project_root
    ).resolve()

    workspaces_dir = _workspaces_dir(
        project_root
    )

    workspaces_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    workspace_dir = (
        workspaces_dir
        / workspace_name
    )

    workspace_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    directory_manager = (
        DirectoryManager(
            root=workspace_dir,
            layout=layout,
        )
    )

    directory_manager.ensure_directories()

    manifest = _write_manifest(
        workspace_name=workspace_name,
        workspace_dir=workspace_dir,
        directory_manager=directory_manager,
    )

    _safe_latest_pointer(
        workspaces_dir,
        workspace_dir,
    )

    (
        project_root
        / RECENT_FILE
    ).write_text(
        workspace_name,
        encoding="utf-8",
    )

    return WorkspacePaths(
        root=workspace_dir,
        workspace_name=workspace_name,
        directories=(
            directory_manager
            .directories()
        ),
        manifest=manifest,
    )


def load_workspace(
    project_root: str | Path,
    workspace_name: str | None = None,
    layout: Dict[str, str | Path] | None = None,
) -> WorkspacePaths:
    """
    Load an existing workspace.

    If workspace_name is not supplied:
        1. .last_workspace is checked
        2. workspaces/latest is checked

    Normally the directory layout is reconstructed from
    workspace.json.

    If the manifest is missing, a layout must be supplied.
    """

    project_root = Path(
        project_root
    ).resolve()

    workspaces_dir = _workspaces_dir(
        project_root
    )

    if workspace_name:

        workspace_dir = (
            workspaces_dir
            / workspace_name
        )

    else:

        recent = (
            project_root
            / RECENT_FILE
        )

        if recent.exists():

            recent_name = (
                recent
                .read_text(
                    encoding="utf-8"
                )
                .strip()
            )

            workspace_dir = (
                workspaces_dir
                / recent_name
            )

        else:

            latest = (
                workspaces_dir
                / LATEST_POINTER
            )

            if latest.is_symlink():

                workspace_dir = (
                    workspaces_dir
                    / latest.readlink()
                ).resolve()

            elif (
                latest.exists()
                and latest.is_file()
            ):

                workspace_dir = Path(
                    latest.read_text(
                        encoding="utf-8"
                    ).strip()
                )

            else:

                raise FileNotFoundError(
                    "No workspace provided and "
                    "no recent/latest workspace found."
                )

    workspace_dir = (
        workspace_dir.resolve()
    )

    if not workspace_dir.exists():
        raise FileNotFoundError(
            f"Workspace not found: "
            f"{workspace_dir}"
        )

    manifest = (
        workspace_dir
        / MANIFEST_FILE
    )

    if manifest.exists():

        data = json.loads(
            manifest.read_text(
                encoding="utf-8"
            )
        )

        workspace_name = data[
            "workspace_name"
        ]

        stored_layout = data.get(
            "directories",
            {},
        )

        directory_manager = (
            DirectoryManager(
                root=workspace_dir,
                layout=stored_layout,
            )
        )

    else:

        if layout is None:
            raise FileNotFoundError(
                f"Workspace manifest missing: "
                f"{manifest}. "
                f"A layout is required to "
                f"reconstruct the workspace."
            )

        workspace_name = (
            workspace_dir.name
        )

        directory_manager = (
            DirectoryManager(
                root=workspace_dir,
                layout=layout,
            )
        )

    directory_manager.ensure_directories()

    return WorkspacePaths(
        root=workspace_dir,
        workspace_name=workspace_name,
        directories=(
            directory_manager
            .directories()
        ),
        manifest=manifest,
    )