"""Generic workspace entry management."""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import json

from framework.workspace.domain_manager import (
    DomainPaths,
)


ENTRY_MANIFEST_FILE = "entry.json"


@dataclass(frozen=True)
class EntryPaths:
    """
    Paths belonging to one domain entry.
    """

    root: Path
    entry_name: str
    manifest: Path


class EntryManager:
    """
    Manage entries inside an existing workspace domain.

    An entry is a named persistent context within a domain.

    EntryManager does not define project-specific entry
    semantics or naming conventions.
    """

    def __init__(
        self,
        domain: DomainPaths,
    ) -> None:

        if not isinstance(
            domain,
            DomainPaths,
        ):
            raise TypeError(
                "domain must be a DomainPaths instance."
            )

        self.domain = domain

    def _validate_entry_name(
        self,
        entry_name: str,
    ) -> str:
        """
        Validate and normalize an entry name.
        """

        if not isinstance(
            entry_name,
            str,
        ):
            raise TypeError(
                "entry_name must be a string."
            )

        entry_name = entry_name.strip()

        if not entry_name:
            raise ValueError(
                "entry_name cannot be empty."
            )

        entry_path = Path(entry_name)

        if (
            entry_path.is_absolute()
            or len(entry_path.parts) != 1
            or entry_name in {".", ".."}
        ):
            raise ValueError(
                "entry_name must be a single directory name."
            )

        return entry_name

    def _write_manifest(
        self,
        entry_name: str,
        root: Path,
    ) -> Path:
        """
        Write the persistent entry manifest.
        """

        manifest = (
            root
            / ENTRY_MANIFEST_FILE
        )

        data = {
            "entry_name": entry_name,
            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        }

        manifest.write_text(
            json.dumps(
                data,
                indent=2,
            ),
            encoding="utf-8",
        )

        return manifest

    def entry_path(
        self,
        entry_name: str,
    ) -> Path:
        """
        Return the path for a domain entry.

        The entry does not need to exist.
        """

        entry_name = self._validate_entry_name(
            entry_name
        )

        return (
            self.domain.root
            / entry_name
        ).resolve()

    def exists(
        self,
        entry_name: str,
    ) -> bool:
        """
        Return True if a managed entry exists.
        """

        root = self.entry_path(
            entry_name
        )

        manifest = (
            root
            / ENTRY_MANIFEST_FILE
        )

        return (
            root.is_dir()
            and manifest.is_file()
        )

    def ensure_entry(
        self,
        entry_name: str,
    ) -> EntryPaths:
        """
        Create an entry if necessary and return its paths.
        """

        entry_name = self._validate_entry_name(
            entry_name
        )

        root = self.entry_path(
            entry_name
        )

        root.mkdir(
            parents=True,
            exist_ok=True,
        )

        manifest = (
            root
            / ENTRY_MANIFEST_FILE
        )

        if not manifest.exists():
            manifest = self._write_manifest(
                entry_name=entry_name,
                root=root,
            )

        return EntryPaths(
            root=root,
            entry_name=entry_name,
            manifest=manifest,
        )

    def load_entry(
        self,
        entry_name: str,
    ) -> EntryPaths:
        """
        Load an existing managed domain entry.
        """

        entry_name = self._validate_entry_name(
            entry_name
        )

        root = self.entry_path(
            entry_name
        )

        if not root.exists():
            raise FileNotFoundError(
                f"Entry not found: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Entry path is not a directory: {root}"
            )

        manifest = (
            root
            / ENTRY_MANIFEST_FILE
        )

        if not manifest.exists():
            raise FileNotFoundError(
                f"Entry manifest missing: {manifest}"
            )

        return EntryPaths(
            root=root,
            entry_name=entry_name,
            manifest=manifest,
        )

    def list_entries(
        self,
    ) -> list[EntryPaths]:
        """
        Return managed entries in this domain.
        """

        entries: list[EntryPaths] = []

        if not self.domain.root.exists():
            return entries

        for path in sorted(
            self.domain.root.iterdir()
        ):
            manifest = (
                path
                / ENTRY_MANIFEST_FILE
            )

            if (
                path.is_dir()
                and manifest.is_file()
            ):
                entries.append(
                    EntryPaths(
                        root=path.resolve(),
                        entry_name=path.name,
                        manifest=manifest.resolve(),
                    )
                )

        return entries