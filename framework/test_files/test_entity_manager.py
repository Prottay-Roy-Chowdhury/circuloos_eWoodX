from pathlib import Path
import json
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
    load_workspace,
)


TEST_PROJECT_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "entity_test_project"
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

entry_1 = entry_manager.ensure_entry(
    "test_entry_001"
)

entity_manager = EntityManager(
    workspace=workspace,
    entry=entry_1,
)

print("Phase 1 - Created hierarchy:")
print(f"  Workspace: {workspace.root}")
print(f"  Domain:    {domain.root}")
print(f"  Entry:     {entry_1.root}")
print(f"  Database:  {entity_manager.database_path}")


# --------------------------------------------------
# Phase 2: Create entities
# --------------------------------------------------

entity_1 = entity_manager.create_entity(
    entity_id="T000001",
    entity_type="timber",
    metadata={
        "color": "brown",
        "length_mm": 1200.0,
    },
)

entity_2 = entity_manager.create_entity(
    entity_id="T000002",
    entity_type="timber",
    metadata={
        "color": "light_brown",
        "length_mm": 1450.0,
    },
)

assert entity_1.root.exists()
assert entity_1.manifest.is_file()

assert entity_2.root.exists()
assert entity_2.manifest.is_file()

assert entity_manager.exists(
    "T000001"
)

assert entity_manager.exists(
    "T000002"
)

print()
print("Phase 2 - Created entities:")
print(f"  T000001: {entity_1.root}")
print(f"  T000002: {entity_2.root}")


# --------------------------------------------------
# Phase 3: Verify entity.json
# --------------------------------------------------

entity_data = json.loads(
    entity_1.manifest.read_text(
        encoding="utf-8"
    )
)

assert entity_data["entity_id"] == "T000001"
assert entity_data["entity_type"] == "timber"

assert (
    entity_data["metadata"]["color"]
    == "brown"
)

assert (
    entity_data["metadata"]["length_mm"]
    == 1200.0
)

print()
print("Phase 3 - entity.json verified:")
print(
    json.dumps(
        entity_data,
        indent=2,
    )
)


# --------------------------------------------------
# Phase 4: Verify SQLite directly
# --------------------------------------------------

assert entity_manager.database_path.is_file()

with sqlite3.connect(
    entity_manager.database_path
) as connection:

    rows = connection.execute(
        """
        SELECT
            entity_id,
            entity_type,
            relative_path
        FROM entities
        ORDER BY entity_id
        """
    ).fetchall()


assert len(rows) == 2

assert rows[0][0] == "T000001"
assert rows[0][1] == "timber"

assert rows[1][0] == "T000002"
assert rows[1][1] == "timber"

print()
print("Phase 4 - SQLite records:")

for row in rows:
    print(
        f"  {row[0]} | "
        f"{row[1]} | "
        f"{row[2]}"
    )


# --------------------------------------------------
# Phase 5: Duplicate identity must fail
# --------------------------------------------------

duplicate_failed = False

try:
    entity_manager.create_entity(
        entity_id="T000001",
        entity_type="timber",
    )

except FileExistsError:
    duplicate_failed = True


assert duplicate_failed

print()
print(
    "Phase 5 - Duplicate entity ID correctly rejected."
)


# --------------------------------------------------
# Phase 6: Create another entry
# --------------------------------------------------

entry_2 = entry_manager.ensure_entry(
    "test_entry_002"
)

entity_manager_2 = EntityManager(
    workspace=workspace,
    entry=entry_2,
)

entity_3 = entity_manager_2.create_entity(
    entity_id="T000003",
    entity_type="timber",
)

assert (
    entity_3.root.parent
    == entry_2.root
)

print()
print("Phase 6 - Entity created in second entry:")
print(f"  T000003: {entity_3.root}")


# --------------------------------------------------
# Phase 7: Cross-entry lookup
# --------------------------------------------------

recovered_entity = (
    entity_manager_2.load_entity(
        "T000001"
    )
)

assert (
    recovered_entity.root
    == entity_1.root
)

assert (
    recovered_entity.root.parent
    == entry_1.root
)

print()
print("Phase 7 - Cross-entry lookup passed:")
print(
    f"  T000001 resolved to: "
    f"{recovered_entity.root}"
)


# --------------------------------------------------
# Phase 8: Simulate application restart
# --------------------------------------------------

del recovered_entity
del entity_3
del entity_2
del entity_1
del entity_manager_2
del entity_manager
del entry_2
del entry_1
del entry_manager
del domain
del domain_manager
del workspace


workspace = load_workspace(
    project_root=TEST_PROJECT_ROOT,
    workspace_name="test_workspace",
)

domain_manager = DomainManager(
    workspace=workspace,
)

domain = domain_manager.load_domain(
    "sensing"
)

entry_manager = EntryManager(
    domain=domain,
)

entry_2 = entry_manager.load_entry(
    "test_entry_002"
)

entity_manager = EntityManager(
    workspace=workspace,
    entry=entry_2,
)

print()
print("Phase 8 - Reloaded hierarchy:")
print(f"  Workspace: {workspace.root}")
print(f"  Domain:    {domain.root}")
print(f"  Entry:     {entry_2.root}")


# --------------------------------------------------
# Phase 9: Recover entities from SQLite
# --------------------------------------------------

entities = entity_manager.list_entities()

entity_ids = [
    entity.entity_id
    for entity in entities
]

assert entity_ids == [
    "T000001",
    "T000002",
    "T000003",
]

recovered_entity = (
    entity_manager.load_entity(
        "T000001"
    )
)

assert recovered_entity.manifest.is_file()

print()
print("Phase 9 - Recovered entities:")

for entity in entities:
    print(
        f"  {entity.entity_id}: "
        f"{entity.root}"
    )


# --------------------------------------------------
# Phase 10: Filter by entity type
# --------------------------------------------------

timber_entities = (
    entity_manager.list_entities(
        entity_type="timber"
    )
)

assert len(timber_entities) == 3

assert {
    entity.entity_id
    for entity in timber_entities
} == {
    "T000001",
    "T000002",
    "T000003",
}

print()
print(
    "Phase 10 - Entity type filtering passed."
)


print()
print(
    "Entity manager persistence test passed."
)