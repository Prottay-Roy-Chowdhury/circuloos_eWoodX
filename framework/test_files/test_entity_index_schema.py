from pathlib import Path
import shutil
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


from framework.workspace import (
    DomainManager,
    EntryManager,
    EntityManager,
    init_workspace,
)


TEST_PROJECT_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "entity_schema_test_project"
)


# --------------------------------------------------
# Clean previous test data
# --------------------------------------------------

if TEST_PROJECT_ROOT.exists():
    shutil.rmtree(TEST_PROJECT_ROOT)


# --------------------------------------------------
# Phase 1: Create hierarchy
# --------------------------------------------------

workspace = init_workspace(
    project_root=TEST_PROJECT_ROOT,
    workspace_name="test_workspace",
    layout={},
)

domain_manager = DomainManager(
    workspace=workspace,
)

domain = domain_manager.ensure_domain(
    "sensing"
)

entry_manager = EntryManager(
    domain=domain,
)

entry = entry_manager.ensure_entry(
    "test_entry_001"
)

print("Phase 1 - Created hierarchy:")
print(f"  Workspace: {workspace.root}")
print(f"  Entry:     {entry.root}")


# --------------------------------------------------
# Phase 2: Initialize first project schema
# --------------------------------------------------

schema_v1 = {
    "color": "TEXT",
    "length_mm": "REAL",
}

entity_manager = EntityManager(
    workspace=workspace,
    entry=entry,
    index_schema=schema_v1,
)

with sqlite3.connect(
    entity_manager.database_path
) as connection:

    columns_v1 = {
        row[1]: row[2]
        for row in connection.execute(
            "PRAGMA table_info(entities)"
        ).fetchall()
    }


assert columns_v1["entity_id"] == "TEXT"
assert columns_v1["entity_type"] == "TEXT"
assert columns_v1["relative_path"] == "TEXT"
assert columns_v1["created_at"] == "TEXT"

assert columns_v1["color"] == "TEXT"
assert columns_v1["length_mm"] == "REAL"


print()
print("Phase 2 - Initial SQLite schema:")

for name, column_type in columns_v1.items():
    print(
        f"  {name}: {column_type}"
    )


# --------------------------------------------------
# Phase 3: Create entity before schema evolution
# --------------------------------------------------

entity = entity_manager.create_entity(
    entity_id="T000001",
    entity_type="timber",
    metadata={
        "color": "brown",
        "length_mm": 1200.0,
    },
)

assert entity.manifest.is_file()

with sqlite3.connect(
    entity_manager.database_path
) as connection:

    row_before = connection.execute(
        """
        SELECT
            entity_id,
            entity_type,
            relative_path,
            created_at
        FROM entities
        WHERE entity_id = ?
        """,
        ("T000001",),
    ).fetchone()


assert row_before is not None
assert row_before[0] == "T000001"
assert row_before[1] == "timber"


print()
print("Phase 3 - Entity created before schema evolution:")
print(f"  Entity: {row_before[0]}")
print(f"  Type:   {row_before[1]}")
print(f"  Path:   {row_before[2]}")


# --------------------------------------------------
# Phase 4: Evolve project schema
# --------------------------------------------------

schema_v2 = {
    "color": "TEXT",
    "length_mm": "REAL",
    "thickness_mm": "REAL",
}

entity_manager_v2 = EntityManager(
    workspace=workspace,
    entry=entry,
    index_schema=schema_v2,
)

with sqlite3.connect(
    entity_manager_v2.database_path
) as connection:

    columns_v2 = {
        row[1]: row[2]
        for row in connection.execute(
            "PRAGMA table_info(entities)"
        ).fetchall()
    }


assert columns_v2["color"] == "TEXT"
assert columns_v2["length_mm"] == "REAL"
assert columns_v2["thickness_mm"] == "REAL"


print()
print("Phase 4 - Evolved SQLite schema:")

for name, column_type in columns_v2.items():
    print(
        f"  {name}: {column_type}"
    )


# --------------------------------------------------
# Phase 5: Existing entity must survive evolution
# --------------------------------------------------

with sqlite3.connect(
    entity_manager_v2.database_path
) as connection:

    row_after = connection.execute(
        """
        SELECT
            entity_id,
            entity_type,
            relative_path,
            created_at,
            thickness_mm
        FROM entities
        WHERE entity_id = ?
        """,
        ("T000001",),
    ).fetchone()


assert row_after is not None

assert row_after[0] == row_before[0]
assert row_after[1] == row_before[1]
assert row_after[2] == row_before[2]
assert row_after[3] == row_before[3]

# Newly added column should contain NULL for
# entities that existed before the column.
assert row_after[4] is None


print()
print(
    "Phase 5 - Existing entity survived schema evolution."
)
print(
    "  New thickness_mm value: "
    f"{row_after[4]}"
)


# --------------------------------------------------
# Phase 6: Existing schema can be reused
# --------------------------------------------------

entity_manager_v3 = EntityManager(
    workspace=workspace,
    entry=entry,
    index_schema=schema_v2,
)

assert entity_manager_v3.exists(
    "T000001"
)

print()
print(
    "Phase 6 - Existing schema reused successfully."
)


# --------------------------------------------------
# Phase 7: Conflicting type must fail
# --------------------------------------------------

conflicting_schema = {
    "color": "TEXT",
    "length_mm": "INTEGER",
    "thickness_mm": "REAL",
}

conflict_failed = False

try:
    EntityManager(
        workspace=workspace,
        entry=entry,
        index_schema=conflicting_schema,
    )

except ValueError as error:
    conflict_failed = True

    print()
    print(
        "Phase 7 - Conflicting schema correctly rejected:"
    )
    print(f"  {error}")


assert conflict_failed


# --------------------------------------------------
# Phase 8: Framework columns cannot be redefined
# --------------------------------------------------

reserved_failed = False

try:
    EntityManager(
        workspace=workspace,
        entry=entry,
        index_schema={
            "entity_id": "TEXT",
        },
    )

except ValueError as error:
    reserved_failed = True

    print()
    print(
        "Phase 8 - Framework column redefinition "
        "correctly rejected:"
    )
    print(f"  {error}")


assert reserved_failed


# --------------------------------------------------
# Phase 9: Invalid SQLite type must fail
# --------------------------------------------------

invalid_type_failed = False

try:
    EntityManager(
        workspace=workspace,
        entry=entry,
        index_schema={
            "length_mm": "VARCHAR",
        },
    )

except ValueError as error:
    invalid_type_failed = True

    print()
    print(
        "Phase 9 - Unsupported SQLite type "
        "correctly rejected:"
    )
    print(f"  {error}")


assert invalid_type_failed


print()
print(
    "Entity index schema evolution test passed."
)