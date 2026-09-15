"""Generic workspace domain management."""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import json

from framework.workspace.workspace_manager import (
    WorkspacePaths,
)

DOMAIN_MANIFEST_FILE = "domain.json"

@dataclass(frozen=True)
class DomainPaths:
    """
    Paths belonging to one workspace domain.
    """

    root: Path
    domain_name: str
    manifest: Path


class DomainManager:
    """
    Manage functional domains inside an existing workspace.

    A domain is a named functional area of a workspace,
    such as sensing, design, robot_control, inspection,
    planning, or fabrication.

    DomainManager only manages the domain boundary.
    It does not define project-specific domain semantics
    or domain history/entry naming.
    """

    def __init__(
        self,
        workspace: WorkspacePaths,
    ) -> None:

        if not isinstance(
            workspace,
            WorkspacePaths,
        ):
            raise TypeError(
                "workspace must be a WorkspacePaths instance."
            )

        self.workspace = workspace

    def _validate_domain_name(
        self,
        domain_name: str,
    ) -> str:
        """
        Validate and normalize a domain name.
        """

        if not isinstance(
            domain_name,
            str,
        ):
            raise TypeError(
                "domain_name must be a string."
            )

        domain_name = domain_name.strip()

        if not domain_name:
            raise ValueError(
                "domain_name cannot be empty."
            )

        domain_path = Path(domain_name)

        if (
            domain_path.is_absolute()
            or len(domain_path.parts) != 1
            or domain_name in {".", ".."}
        ):
            raise ValueError(
                "domain_name must be a single directory name."
            )

        return domain_name

    def _write_manifest(
        self,
        domain_name: str,
        root: Path,
    ) -> Path:
        """
        Write the persistent domain manifest.
        """

        manifest = (
            root
            / DOMAIN_MANIFEST_FILE
        )

        data = {
            "domain_name": domain_name,
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

    def domain_path(
        self,
        domain_name: str,
    ) -> Path:
        """
        Return the path for a workspace domain.

        The domain does not need to exist.
        """

        domain_name = self._validate_domain_name(
            domain_name
        )

        return (
            self.workspace.root
            / domain_name
        ).resolve()

    def exists(
        self,
        domain_name: str,
    ) -> bool:
        """
        Return True if a managed domain exists.
        """

        root = self.domain_path(
            domain_name
        )

        manifest = (
            root
            / DOMAIN_MANIFEST_FILE
        )

        return (
            root.is_dir()
            and manifest.is_file()
        )

    def ensure_domain(
        self,
        domain_name: str,
    ) -> DomainPaths:
        """
        Create a domain if necessary and return its paths.
        """

        domain_name = self._validate_domain_name(
            domain_name
        )

        root = self.domain_path(
            domain_name
        )

        root.mkdir(
            parents=True,
            exist_ok=True,
        )

        manifest = (
            root
            / DOMAIN_MANIFEST_FILE
        )

        if not manifest.exists():
            manifest = self._write_manifest(
                domain_name=domain_name,
                root=root,
            )

        return DomainPaths(
            root=root,
            domain_name=domain_name,
            manifest=manifest,
        )

    def load_domain(
        self,
        domain_name: str,
    ) -> DomainPaths:
        """
        Load an existing workspace domain.
        """

        domain_name = self._validate_domain_name(
            domain_name
        )

        root = self.domain_path(
            domain_name
        )

        if not root.exists():
            raise FileNotFoundError(
                f"Domain not found: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Domain path is not a directory: {root}"
            )

        manifest = (
            root
            / DOMAIN_MANIFEST_FILE
        )

        if not manifest.exists():
            raise FileNotFoundError(
                f"Domain manifest missing: {manifest}"
            )

        return DomainPaths(
            root=root,
            domain_name=domain_name,
            manifest=manifest,
        )

    def list_domains(
        self,
    ) -> list[DomainPaths]:
        """
        Return managed workspace domains.
        """

        domains: list[DomainPaths] = []

        if not self.workspace.root.exists():
            return domains

        for path in sorted(
            self.workspace.root.iterdir()
        ):
            manifest = (
                path
                / DOMAIN_MANIFEST_FILE
            )

            if (
                path.is_dir()
                and manifest.exists()
            ):
                domains.append(
                    DomainPaths(
                        root=path.resolve(),
                        domain_name=path.name,
                        manifest=manifest.resolve(),
                    )
                )

        return domains