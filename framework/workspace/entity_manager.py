"""Generic persistent entity management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import sqlite3

from framework.workspace.entry_manager import EntryPaths
from framework.workspace.workspace_manager import WorkspacePaths


ENTITY_MANIFEST_FILE = "entity.json"

INDEX_DIRECTORY = "index"
ENTITY_DATABASE_FILE = "entities.db"

SQLITE_TYPES = {
    "TEXT",
    "INTEGER",
    "REAL",
    "BLOB",
}

BASE_COLUMNS = {
    "entity_id",
    "entity_type",
    "relative_path",
    "created_at",
}


@dataclass(frozen=True)
class EntityPaths:
    """
    Paths belonging to one persistent entity.
    """

    root: Path
    entity_id: str
    manifest: Path


class EntityManager:
    """
    Manage persistent entities associated with an entry.

    Entity metadata is stored locally with the entity.
    A workspace-level SQLite database provides persistent
    entity discovery and lookup.
    """

    def __init__(
        self,
        workspace: WorkspacePaths,
        entry: EntryPaths,
        index_schema: dict[str, str] | None = None,
    ) -> None:

        if not isinstance(
            workspace,
            WorkspacePaths,
        ):
            raise TypeError(
                "workspace must be a WorkspacePaths instance."
            )

        if not isinstance(
            entry,
            EntryPaths,
        ):
            raise TypeError(
                "entry must be an EntryPaths instance."
            )

        self.workspace = workspace
        self.entry = entry

        self.index_schema = self._validate_index_schema(
            index_schema or {}
        )

        self.index_directory = (
            self.workspace.root
            / INDEX_DIRECTORY
        )

        self.database_path = (
            self.index_directory
            / ENTITY_DATABASE_FILE
        )

        self._initialize_database()

    def _validate_index_schema(
        self,
        index_schema: dict[str, str],
    ) -> dict[str, str]:
        """
        Validate project-defined SQLite index columns.
        """

        if not isinstance(
            index_schema,
            dict,
        ):
            raise TypeError(
                "index_schema must be a dictionary."
            )

        validated: dict[str, str] = {}

        for column_name, column_type in index_schema.items():

            if not isinstance(
                column_name,
                str,
            ):
                raise TypeError(
                    "SQLite column names must be strings."
                )

            column_name = column_name.strip()

            if not column_name:
                raise ValueError(
                    "SQLite column names cannot be empty."
                )

            if not column_name.isidentifier():
                raise ValueError(
                    f"Invalid SQLite column name: {column_name}"
                )

            if column_name in BASE_COLUMNS:
                raise ValueError(
                    f"Project index schema cannot redefine "
                    f"framework column: {column_name}"
                )

            if not isinstance(
                column_type,
                str,
            ):
                raise TypeError(
                    "SQLite column types must be strings."
                )

            column_type = column_type.strip().upper()

            if column_type not in SQLITE_TYPES:
                raise ValueError(
                    f"Unsupported SQLite type: {column_type}"
                )

            validated[column_name] = column_type

        return validated

    def _initialize_database(
        self,
    ) -> None:
        """
        Create and evolve the entity database if necessary.
        """

        self.index_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            existing_columns = {
                row[1]: row[2].upper()
                for row in connection.execute(
                    "PRAGMA table_info(entities)"
                ).fetchall()
            }

            for (
                column_name,
                column_type,
            ) in self.index_schema.items():

                if column_name in existing_columns:

                    existing_type = (
                        existing_columns[column_name]
                    )

                    if existing_type != column_type:
                        raise ValueError(
                            f"SQLite column '{column_name}' "
                            f"already exists as {existing_type}, "
                            f"but project schema requests "
                            f"{column_type}."
                        )

                    continue

                connection.execute(
                    f"""
                    ALTER TABLE entities
                    ADD COLUMN {column_name} {column_type}
                    """
                )

    def _validate_entity_id(
        self,
        entity_id: str,
    ) -> str:
        """
        Validate and normalize an entity identifier.
        """

        if not isinstance(
            entity_id,
            str,
        ):
            raise TypeError(
                "entity_id must be a string."
            )

        entity_id = entity_id.strip()

        if not entity_id:
            raise ValueError(
                "entity_id cannot be empty."
            )

        entity_path = Path(entity_id)

        if (
            entity_path.is_absolute()
            or len(entity_path.parts) != 1
            or entity_id in {".", ".."}
        ):
            raise ValueError(
                "entity_id must be a single directory name."
            )

        return entity_id

    def _validate_entity_type(
        self,
        entity_type: str,
    ) -> str:
        """
        Validate and normalize an entity type.
        """

        if not isinstance(
            entity_type,
            str,
        ):
            raise TypeError(
                "entity_type must be a string."
            )

        entity_type = entity_type.strip()

        if not entity_type:
            raise ValueError(
                "entity_type cannot be empty."
            )

        return entity_type

    def entity_path(
        self,
        entity_id: str,
    ) -> Path:
        """
        Return the operational path for an entity.
        """

        entity_id = self._validate_entity_id(
            entity_id
        )

        return (
            self.entry.root
            / entity_id
        ).resolve()

    def _write_manifest(
        self,
        entity_id: str,
        entity_type: str,
        root: Path,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """
        Write the canonical entity manifest.
        """

        manifest = (
            root
            / ENTITY_MANIFEST_FILE
        )

        data = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "metadata": metadata or {},
        }

        manifest.write_text(
            json.dumps(
                data,
                indent=2,
            ),
            encoding="utf-8",
        )

        return manifest

    def _register_entity(
        self,
        entity_id: str,
        entity_type: str,
        root: Path,
        created_at: str,
    ) -> None:
        """
        Register an entity in the workspace index.
        """

        relative_path = root.relative_to(
            self.workspace.root
        )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            connection.execute(
                """
                INSERT INTO entities (
                    entity_id,
                    entity_type,
                    relative_path,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    entity_id,
                    entity_type,
                    relative_path.as_posix(),
                    created_at,
                ),
            )

    def create_entity(
        self,
        entity_id: str,
        entity_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> EntityPaths:
        """
        Create and register a new persistent entity.
        """

        entity_id = self._validate_entity_id(
            entity_id
        )

        entity_type = self._validate_entity_type(
            entity_type
        )

        if self.exists(
            entity_id
        ):
            raise FileExistsError(
                f"Entity already exists: {entity_id}"
            )

        root = self.entity_path(
            entity_id
        )

        root.mkdir(
            parents=True,
            exist_ok=False,
        )

        manifest = self._write_manifest(
            entity_id=entity_id,
            entity_type=entity_type,
            root=root,
            metadata=metadata,
        )

        data = json.loads(
            manifest.read_text(
                encoding="utf-8"
            )
        )

        self._register_entity(
            entity_id=entity_id,
            entity_type=entity_type,
            root=root,
            created_at=data["created_at"],
        )

        return EntityPaths(
            root=root,
            entity_id=entity_id,
            manifest=manifest,
        )

    def exists(
        self,
        entity_id: str,
    ) -> bool:
        """
        Return True if an entity is registered.
        """

        entity_id = self._validate_entity_id(
            entity_id
        )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            row = connection.execute(
                """
                SELECT entity_id
                FROM entities
                WHERE entity_id = ?
                """,
                (entity_id,),
            ).fetchone()

        return row is not None

    def load_entity(
        self,
        entity_id: str,
    ) -> EntityPaths:
        """
        Locate and load a registered entity.
        """

        entity_id = self._validate_entity_id(
            entity_id
        )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            row = connection.execute(
                """
                SELECT relative_path
                FROM entities
                WHERE entity_id = ?
                """,
                (entity_id,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(
                f"Entity not registered: {entity_id}"
            )

        root = (
            self.workspace.root
            / row[0]
        ).resolve()

        manifest = (
            root
            / ENTITY_MANIFEST_FILE
        )

        if not root.is_dir():
            raise FileNotFoundError(
                f"Entity directory missing: {root}"
            )

        if not manifest.is_file():
            raise FileNotFoundError(
                f"Entity manifest missing: {manifest}"
            )

        return EntityPaths(
            root=root,
            entity_id=entity_id,
            manifest=manifest,
        )

    def list_entities(
        self,
        entity_type: str | None = None,
    ) -> list[EntityPaths]:
        """
        Return registered entities.

        Optionally filter by entity type.
        """

        with sqlite3.connect(
            self.database_path
        ) as connection:

            if entity_type is None:

                rows = connection.execute(
                    """
                    SELECT entity_id, relative_path
                    FROM entities
                    ORDER BY entity_id
                    """
                ).fetchall()

            else:

                entity_type = self._validate_entity_type(
                    entity_type
                )

                rows = connection.execute(
                    """
                    SELECT entity_id, relative_path
                    FROM entities
                    WHERE entity_type = ?
                    ORDER BY entity_id
                    """,
                    (entity_type,),
                ).fetchall()

        entities: list[EntityPaths] = []

        for entity_id, relative_path in rows:

            root = (
                self.workspace.root
                / relative_path
            ).resolve()

            manifest = (
                root
                / ENTITY_MANIFEST_FILE
            )

            if (
                root.is_dir()
                and manifest.is_file()
            ):
                entities.append(
                    EntityPaths(
                        root=root,
                        entity_id=entity_id,
                        manifest=manifest,
                    )
                )

        return entities