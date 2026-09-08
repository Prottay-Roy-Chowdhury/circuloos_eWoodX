"""Generic workspace directory management."""

from __future__ import annotations

from pathlib import Path
from typing import Dict


class DirectoryManager:
    """
    Manage a project-defined directory layout inside a workspace.

    The framework does not assign meaning to directory keys or paths.
    Projects provide the layout.
    """

    def __init__(
        self,
        root: str | Path,
        layout: Dict[str, str | Path],
    ):
        self.root = Path(root).resolve()

        if not isinstance(layout, dict):
            raise TypeError(
                "layout must be a dictionary."
            )

        self.layout = self._validate_layout(
            layout
        )

    def _validate_layout(
        self,
        layout: Dict[str, str | Path],
    ) -> Dict[str, Path]:

        validated: Dict[str, Path] = {}

        for key, relative_path in layout.items():

            if not isinstance(key, str):
                raise TypeError(
                    "Directory layout keys must be strings."
                )

            key = key.strip()

            if not key:
                raise ValueError(
                    "Directory layout keys cannot be empty."
                )

            path = Path(relative_path)

            if path.is_absolute():
                raise ValueError(
                    f"Directory path must be relative: "
                    f"{relative_path}"
                )

            if ".." in path.parts:
                raise ValueError(
                    f"Directory path cannot leave the "
                    f"workspace root: {relative_path}"
                )

            validated[key] = path

        return validated

    def ensure_directories(self) -> None:
        """
        Create the workspace root and all configured directories.
        """

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        for relative_path in self.layout.values():

            directory = (
                self.root
                / relative_path
            )

            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

    def directory(
        self,
        key: str,
    ) -> Path:
        """
        Return the absolute path for a configured directory.
        """

        if key not in self.layout:
            raise KeyError(
                f"Unknown directory key: {key}"
            )

        return (
            self.root
            / self.layout[key]
        ).resolve()

    def directories(
        self,
    ) -> Dict[str, Path]:
        """
        Return all configured directory paths.
        """

        return {
            key: (
                self.root
                / relative_path
            ).resolve()
            for key, relative_path
            in self.layout.items()
        }

    def relative_layout(
        self,
    ) -> Dict[str, str]:
        """
        Return the directory layout in serializable form.
        """

        return {
            key: str(path)
            for key, path
            in self.layout.items()
        }