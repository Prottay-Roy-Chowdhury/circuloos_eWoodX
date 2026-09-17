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
    "availability_status",
    "claimed_by",
}

ENTITY_STATUS_AVAILABLE = "available"
ENTITY_STATUS_CLAIMED = "claimed"
ENTITY_STATUS_UNAVAILABLE = "unavailable"

ENTITY_STATUSES = {
    ENTITY_STATUS_AVAILABLE,
    ENTITY_STATUS_CLAIMED,
    ENTITY_STATUS_UNAVAILABLE,
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
                    created_at TEXT NOT NULL,
                    availability_status TEXT NOT NULL DEFAULT 'available',
                    claimed_by TEXT
                )
                """
            )

            existing_columns = {
                row[1]: row[2].upper()
                for row in connection.execute(
                    "PRAGMA table_info(entities)"
                ).fetchall()
            }

            if "availability_status" not in existing_columns:
                connection.execute(
                    """
                    ALTER TABLE entities
                    ADD COLUMN availability_status
                    TEXT NOT NULL DEFAULT 'available'
                    """
                )

            if "claimed_by" not in existing_columns:
                connection.execute(
                    """
                    ALTER TABLE entities
                    ADD COLUMN claimed_by TEXT
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
            "availability_status": ENTITY_STATUS_AVAILABLE,
            "claimed_by": None,
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
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Register an entity in the workspace index.

        Project-defined metadata fields are indexed only
        when they are declared in index_schema.
        """

        relative_path = root.relative_to(
            self.workspace.root
        )

        metadata = metadata or {}

        columns = [
            "entity_id",
            "entity_type",
            "relative_path",
            "created_at",
            "availability_status",
            "claimed_by",
        ]

        values = [
            entity_id,
            entity_type,
            relative_path.as_posix(),
            created_at,
            ENTITY_STATUS_AVAILABLE,
            None,
        ]

        for column_name in self.index_schema:

            columns.append(
                column_name
            )

            values.append(
                metadata.get(
                    column_name
                )
            )

        placeholders = ", ".join(
            "?"
            for _ in values
        )

        column_names = ", ".join(
            columns
        )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            connection.execute(
                f"""
                INSERT INTO entities (
                    {column_names}
                )
                VALUES (
                    {placeholders}
                )
                """,
                values,
            )

    def _set_availability_state(
        self,
        entity_id: str,
        availability_status: str,
        claimed_by: str | None,
    ) -> EntityPaths:
        """
        Persist entity availability state to the canonical
        manifest and workspace SQLite index.
        """

        entity = self.load_entity(
            entity_id
        )

        with entity.manifest.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

        data["availability_status"] = (
            availability_status
        )

        data["claimed_by"] = (
            claimed_by
        )

        temporary_path = (
            entity.manifest.with_suffix(
                entity.manifest.suffix + ".tmp"
            )
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        temporary_path.replace(
            entity.manifest
        )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            connection.execute(
                """
                UPDATE entities
                SET
                    availability_status = ?,
                    claimed_by = ?
                WHERE entity_id = ?
                """,
                (
                    availability_status,
                    claimed_by,
                    entity_id,
                ),
            )

        return entity

    def _write_availability_manifest(
        self,
        entity: EntityPaths,
        availability_status: str,
        claimed_by: str | None,
    ) -> None:

        with entity.manifest.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

        data["availability_status"] = (
            availability_status
        )

        data["claimed_by"] = (
            claimed_by
        )

        temporary_path = (
            entity.manifest.with_suffix(
                entity.manifest.suffix + ".tmp"
            )
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        temporary_path.replace(
            entity.manifest
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
            metadata=metadata,
        )

        return EntityPaths(
            root=root,
            entity_id=entity_id,
            manifest=manifest,
        )

    def claim_entity(
        self,
        entity_id: str,
        claimed_by: str,
    ) -> EntityPaths:
        """
        Claim an available entity for a consumer.
        """

        entity_id = self._validate_entity_id(
            entity_id
        )

        claimed_by = str(
            claimed_by or ""
        ).strip()

        if not claimed_by:
            raise ValueError(
                "claimed_by cannot be empty."
            )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            cursor = connection.execute(
                """
                UPDATE entities
                SET
                    availability_status = ?,
                    claimed_by = ?
                WHERE entity_id = ?
                AND availability_status = ?
                """,
                (
                    ENTITY_STATUS_CLAIMED,
                    claimed_by,
                    entity_id,
                    ENTITY_STATUS_AVAILABLE,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Entity is not available: {entity_id}"
                )

        entity = self.load_entity(
            entity_id
        )

        self._write_availability_manifest(
            entity=entity,
            availability_status=ENTITY_STATUS_CLAIMED,
            claimed_by=claimed_by,
        )

        return entity

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

    def release_entity(
        self,
        entity_id: str,
        claimed_by: str,
    ) -> EntityPaths:
        """
        Release a claimed entity back to available state.
        """

        entity_id = self._validate_entity_id(
            entity_id
        )

        claimed_by = str(
            claimed_by or ""
        ).strip()

        if not claimed_by:
            raise ValueError(
                "claimed_by cannot be empty."
            )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            cursor = connection.execute(
                """
                UPDATE entities
                SET
                    availability_status = ?,
                    claimed_by = NULL
                WHERE entity_id = ?
                AND availability_status = ?
                AND claimed_by = ?
                """,
                (
                    ENTITY_STATUS_AVAILABLE,
                    entity_id,
                    ENTITY_STATUS_CLAIMED,
                    claimed_by,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Entity is not claimed by this consumer."
                )

        entity = self.load_entity(
            entity_id
        )

        self._write_availability_manifest(
            entity=entity,
            availability_status=ENTITY_STATUS_AVAILABLE,
            claimed_by=None,
        )

        return entity

    def mark_unavailable(
        self,
        entity_id: str,
        claimed_by: str,
    ) -> EntityPaths:
        """
        Mark a claimed entity as unavailable.
        """

        entity_id = self._validate_entity_id(
            entity_id
        )

        claimed_by = str(
            claimed_by or ""
        ).strip()

        if not claimed_by:
            raise ValueError(
                "claimed_by cannot be empty."
            )

        with sqlite3.connect(
            self.database_path
        ) as connection:

            cursor = connection.execute(
                """
                UPDATE entities
                SET
                    availability_status = ?,
                    claimed_by = NULL
                WHERE entity_id = ?
                AND availability_status = ?
                AND claimed_by = ?
                """,
                (
                    ENTITY_STATUS_UNAVAILABLE,
                    entity_id,
                    ENTITY_STATUS_CLAIMED,
                    claimed_by,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Entity is not claimed by this consumer."
                )

        entity = self.load_entity(
            entity_id
        )

        self._write_availability_manifest(
            entity=entity,
            availability_status=ENTITY_STATUS_UNAVAILABLE,
            claimed_by=None,
        )

        return entity

    def set_availability(
        self,
        entity_id: str,
        availability_status: str,
    ) -> EntityPaths:
        """
        Explicitly override entity availability.

        Intended for administrative, testing, and simulation use.
        """

        entity_id = self._validate_entity_id(
            entity_id
        )

        availability_status = str(
            availability_status or ""
        ).strip().lower()

        if availability_status not in {
            ENTITY_STATUS_AVAILABLE,
            ENTITY_STATUS_UNAVAILABLE,
        }:
            raise ValueError(
                "Manual availability must be "
                "'available' or 'unavailable'."
            )

        return self._set_availability_state(
            entity_id=entity_id,
            availability_status=availability_status,
            claimed_by=None,
        )

    def query_entities(
        self,
        filters: dict[str, Any] | None = None,
    ) -> list[EntityPaths]:
        """
        Query registered entities using exact-match filters.

        Filters may reference framework-owned columns or
        project-defined indexed columns.
        """

        filters = filters or {}

        if not isinstance(
            filters,
            dict,
        ):
            raise TypeError(
                "filters must be a dictionary."
            )

        allowed_columns = (
            BASE_COLUMNS
            | set(self.index_schema)
        )

        conditions: list[str] = []
        values: list[Any] = []

        for column_name, value in filters.items():

            if column_name not in allowed_columns:
                raise ValueError(
                    f"Column is not indexed: {column_name}"
                )

            if value is None:
                conditions.append(
                    f"{column_name} IS NULL"
                )
            else:
                conditions.append(
                    f"{column_name} = ?"
                )

                values.append(
                    value
                )

        query = """
            SELECT
                entity_id,
                relative_path
            FROM entities
        """

        if conditions:
            query += (
                " WHERE "
                + " AND ".join(conditions)
            )

        query += " ORDER BY entity_id"

        with sqlite3.connect(
            self.database_path
        ) as connection:

            rows = connection.execute(
                query,
                values,
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