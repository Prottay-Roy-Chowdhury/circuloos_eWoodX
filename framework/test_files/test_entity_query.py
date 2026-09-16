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
)


TEST_PROJECT_ROOT = (
    PROJECT_ROOT
    / "test_file_transfer_data"
    / "test_data"
    / "entity_query_test_project"
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


# --------------------------------------------------
# Phase 2: Project-defined index schema
# --------------------------------------------------

index_schema = {
    "color": "TEXT",
    "length_mm": "REAL",
    "width_mm": "REAL",
    "thickness_mm": "REAL",
    "area_mm2": "REAL",
}

entity_manager = EntityManager(
    workspace=workspace,
    entry=entry,
    index_schema=index_schema,
)

print("Phase 1 - Created hierarchy:")
print(f"  Workspace: {workspace.root}")
print(f"  Entry:     {entry.root}")
print(f"  Database:  {entity_manager.database_path}")

print()
print("Phase 2 - Project index schema:")

for name, column_type in index_schema.items():
    print(f"  {name}: {column_type}")


# --------------------------------------------------
# Phase 3: Create entities
# --------------------------------------------------

entity_1 = entity_manager.create_entity(
    entity_id="T000001",
    entity_type="timber",
    metadata={
        "color": "brown",
        "length_mm": 1200.0,
        "width_mm": 180.0,
        "thickness_mm": 35.0,
        "area_mm2": 210000.0,
        "species": "pine",
        "source": "reclaimed",
    },
)

entity_2 = entity_manager.create_entity(
    entity_id="T000002",
    entity_type="timber",
    metadata={
        "color": "brown",
        "length_mm": 1500.0,
        "width_mm": 200.0,
        "thickness_mm": 40.0,
        "area_mm2": 290000.0,
        "species": "oak",
        "source": "reclaimed",
    },
)

# Deliberately omit thickness_mm and area_mm2.
entity_3 = entity_manager.create_entity(
    entity_id="T000003",
    entity_type="timber",
    metadata={
        "color": "light_brown",
        "length_mm": 900.0,
        "width_mm": 160.0,
        "species": "pine",
        "source": "reclaimed",
    },
)

print()
print("Phase 3 - Created entities:")
print(f"  {entity_1.entity_id}")
print(f"  {entity_2.entity_id}")
print(f"  {entity_3.entity_id}")


# --------------------------------------------------
# Phase 4: Verify canonical entity.json
# --------------------------------------------------

entity_1_data = json.loads(
    entity_1.manifest.read_text(
        encoding="utf-8"
    )
)

assert entity_1_data["metadata"]["color"] == "brown"
assert entity_1_data["metadata"]["length_mm"] == 1200.0
assert entity_1_data["metadata"]["species"] == "pine"
assert entity_1_data["metadata"]["source"] == "reclaimed"

print()
print(
    "Phase 4 - Canonical entity.json retains "
    "all metadata."
)


# --------------------------------------------------
# Phase 5: Verify SQLite projection
# --------------------------------------------------

with sqlite3.connect(
    entity_manager.database_path
) as connection:

    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(entities)"
        ).fetchall()
    }

    rows = connection.execute(
        """
        SELECT
            entity_id,
            color,
            length_mm,
            width_mm,
            thickness_mm,
            area_mm2
        FROM entities
        ORDER BY entity_id
        """
    ).fetchall()


# Indexed properties must exist as columns.
assert "color" in columns
assert "length_mm" in columns
assert "width_mm" in columns
assert "thickness_mm" in columns
assert "area_mm2" in columns

# Non-indexed metadata must not become columns.
assert "species" not in columns
assert "source" not in columns


assert rows[0] == (
    "T000001",
    "brown",
    1200.0,
    180.0,
    35.0,
    210000.0,
)

assert rows[1] == (
    "T000002",
    "brown",
    1500.0,
    200.0,
    40.0,
    290000.0,
)

assert rows[2] == (
    "T000003",
    "light_brown",
    900.0,
    160.0,
    None,
    None,
)


print()
print("Phase 5 - SQLite metadata projection:")

for row in rows:
    print(f"  {row}")


# --------------------------------------------------
# Phase 6: Query project-defined property
# --------------------------------------------------

brown_entities = entity_manager.query_entities(
    filters={
        "color": "brown",
    }
)

brown_ids = [
    entity.entity_id
    for entity in brown_entities
]

assert brown_ids == [
    "T000001",
    "T000002",
]

print()
print("Phase 6 - Query color='brown':")
print(f"  {brown_ids}")


# --------------------------------------------------
# Phase 7: Query framework-owned property
# --------------------------------------------------

timber_entities = entity_manager.query_entities(
    filters={
        "entity_type": "timber",
    }
)

timber_ids = [
    entity.entity_id
    for entity in timber_entities
]

assert timber_ids == [
    "T000001",
    "T000002",
    "T000003",
]

print()
print("Phase 7 - Query entity_type='timber':")
print(f"  {timber_ids}")


# --------------------------------------------------
# Phase 8: Combined query
# --------------------------------------------------

combined_entities = entity_manager.query_entities(
    filters={
        "entity_type": "timber",
        "color": "brown",
        "thickness_mm": 35.0,
    }
)

combined_ids = [
    entity.entity_id
    for entity in combined_entities
]

assert combined_ids == [
    "T000001",
]

print()
print("Phase 8 - Combined query:")
print(f"  {combined_ids}")


# --------------------------------------------------
# Phase 9: Query missing indexed value
# --------------------------------------------------

missing_thickness = entity_manager.query_entities(
    filters={
        "thickness_mm": None,
    }
)

missing_thickness_ids = [
    entity.entity_id
    for entity in missing_thickness
]

assert missing_thickness_ids == [
    "T000003",
]

print()
print("Phase 9 - Query thickness_mm IS NULL:")
print(f"  {missing_thickness_ids}")


# --------------------------------------------------
# Phase 10: Empty filters return all entities
# --------------------------------------------------

all_entities = entity_manager.query_entities()

all_ids = [
    entity.entity_id
    for entity in all_entities
]

assert all_ids == [
    "T000001",
    "T000002",
    "T000003",
]

print()
print("Phase 10 - Query without filters:")
print(f"  {all_ids}")


# --------------------------------------------------
# Phase 11: Non-indexed metadata cannot be queried
# --------------------------------------------------

non_indexed_failed = False

try:
    entity_manager.query_entities(
        filters={
            "species": "pine",
        }
    )

except ValueError as error:
    non_indexed_failed = True

    print()
    print(
        "Phase 11 - Non-indexed property "
        "correctly rejected:"
    )
    print(f"  {error}")


assert non_indexed_failed


# --------------------------------------------------
# Phase 12: Persistence after reconstruction
# --------------------------------------------------

del entity_manager
del entity_1
del entity_2
del entity_3


entity_manager = EntityManager(
    workspace=workspace,
    entry=entry,
    index_schema=index_schema,
)

recovered = entity_manager.query_entities(
    filters={
        "color": "brown",
    }
)

recovered_ids = [
    entity.entity_id
    for entity in recovered
]

assert recovered_ids == [
    "T000001",
    "T000002",
]

print()
print(
    "Phase 12 - Query persisted after "
    "manager reconstruction:"
)
print(f"  {recovered_ids}")


print()
print(
    "Entity metadata indexing and query test passed."
)