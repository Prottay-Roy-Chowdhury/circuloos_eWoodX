from pathlib import Path
import shutil
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
    / "entity_query_comparison_test_project"
)


def entity_ids(entities):
    return [
        entity.entity_id
        for entity in entities
    ]


def main():

    # --------------------------------------------------
    # Clean previous test data
    # --------------------------------------------------

    if TEST_PROJECT_ROOT.exists():
        shutil.rmtree(
            TEST_PROJECT_ROOT
        )

    # --------------------------------------------------
    # Phase 1
    # Create hierarchy
    # --------------------------------------------------

    workspace = init_workspace(
        project_root=TEST_PROJECT_ROOT,
        workspace_name="test_workspace",
        layout={},
    )

    domain_manager = DomainManager(
        workspace=workspace
    )

    domain = domain_manager.ensure_domain(
        "sensing"
    )

    entry_manager = EntryManager(
        domain=domain
    )

    entry = entry_manager.ensure_entry(
        "test_entry_001"
    )

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

    print(
        "\nPhase 1 - Created hierarchy:"
    )
    print(
        f"  Workspace: {workspace.root}"
    )
    print(
        f"  Database:  {entity_manager.database_path}"
    )

    # --------------------------------------------------
    # Phase 2
    # Create timber inventory
    # --------------------------------------------------

    entity_manager.create_entity(
        entity_id="T000001",
        entity_type="timber",
        metadata={
            "color": "brown",
            "length_mm": 1500.0,
            "width_mm": 200.0,
            "thickness_mm": 40.0,
            "area_mm2": 300000.0,
        },
    )

    entity_manager.create_entity(
        entity_id="T000002",
        entity_type="timber",
        metadata={
            "color": "brown",
            "length_mm": 1000.0,
            "width_mm": 250.0,
            "thickness_mm": 40.0,
            "area_mm2": 250000.0,
        },
    )

    entity_manager.create_entity(
        entity_id="T000003",
        entity_type="timber",
        metadata={
            "color": "dark_brown",
            "length_mm": 1800.0,
            "width_mm": 220.0,
            "thickness_mm": 45.0,
            "area_mm2": 396000.0,
        },
    )

    entity_manager.create_entity(
        entity_id="T000004",
        entity_type="timber",
        metadata={
            "color": "light_brown",
            "length_mm": 1600.0,
            "width_mm": 170.0,
            "thickness_mm": 35.0,
            "area_mm2": 272000.0,
        },
    )

    entity_manager.create_entity(
        entity_id="T000005",
        entity_type="timber",
        metadata={
            "color": "brown",
            "length_mm": 1200.0,
            "width_mm": 180.0,
            # thickness intentionally missing
            "area_mm2": 216000.0,
        },
    )

    print(
        "\nPhase 2 - Created T000001 through T000005."
    )

    # --------------------------------------------------
    # Phase 3
    # Greater than
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "length_mm": {
                "gt": 1500.0,
            }
        }
    )

    assert entity_ids(result) == [
        "T000003",
        "T000004",
    ]

    print(
        "\nPhase 3 - length_mm > 1500:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 4
    # Greater than or equal
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "length_mm": {
                "gte": 1500.0,
            }
        }
    )

    assert entity_ids(result) == [
        "T000001",
        "T000003",
        "T000004",
    ]

    print(
        "\nPhase 4 - length_mm >= 1500:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 5
    # Less than
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "width_mm": {
                "lt": 200.0,
            }
        }
    )

    assert entity_ids(result) == [
        "T000004",
        "T000005",
    ]

    print(
        "\nPhase 5 - width_mm < 200:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 6
    # Less than or equal
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "thickness_mm": {
                "lte": 40.0,
            }
        }
    )

    assert entity_ids(result) == [
        "T000001",
        "T000002",
        "T000004",
    ]

    print(
        "\nPhase 6 - thickness_mm <= 40:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 7
    # Explicit equality operator
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "color": {
                "eq": "brown",
            }
        }
    )

    assert entity_ids(result) == [
        "T000001",
        "T000002",
        "T000005",
    ]

    print(
        "\nPhase 7 - color == brown:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 8
    # Not equal
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "color": {
                "ne": "brown",
            }
        }
    )

    assert entity_ids(result) == [
        "T000003",
        "T000004",
    ]

    print(
        "\nPhase 8 - color != brown:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 9
    # Existing simple equality syntax still works
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "color": "brown",
        }
    )

    assert entity_ids(result) == [
        "T000001",
        "T000002",
        "T000005",
    ]

    print(
        "\nPhase 9 - Existing equality syntax:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 10
    # Existing NULL syntax still works
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "thickness_mm": None,
        }
    )

    assert entity_ids(result) == [
        "T000005"
    ]

    print(
        "\nPhase 10 - thickness_mm IS NULL:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 11
    # Explicit eq None
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "thickness_mm": {
                "eq": None,
            }
        }
    )

    assert entity_ids(result) == [
        "T000005"
    ]

    print(
        "\nPhase 11 - explicit eq None:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 12
    # Explicit ne None
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "thickness_mm": {
                "ne": None,
            }
        }
    )

    assert entity_ids(result) == [
        "T000001",
        "T000002",
        "T000003",
        "T000004",
    ]

    print(
        "\nPhase 12 - thickness_mm IS NOT NULL:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 13
    # Real material-selection query
    # --------------------------------------------------

    result = entity_manager.query_entities(
        filters={
            "entity_type": "timber",
            "availability_status": "available",
            "length_mm": {
                "gte": 1200.0,
            },
            "width_mm": {
                "gte": 180.0,
            },
            "thickness_mm": {
                "gte": 35.0,
            },
        }
    )

    assert entity_ids(result) == [
        "T000001",
        "T000003",
    ]

    print(
        "\nPhase 13 - Suitable available timber:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 14
    # Claim geometrically suitable timber
    # --------------------------------------------------

    entity_manager.claim_entity(
        entity_id="T000003",
        claimed_by="design_agent_A",
    )

    result = entity_manager.query_entities(
        filters={
            "entity_type": "timber",
            "availability_status": "available",
            "length_mm": {
                "gte": 1200.0,
            },
            "width_mm": {
                "gte": 180.0,
            },
            "thickness_mm": {
                "gte": 35.0,
            },
        }
    )

    assert entity_ids(result) == [
        "T000001"
    ]

    print(
        "\nPhase 14 - After T000003 is claimed:"
    )
    print(
        f"  Suitable available timber: {entity_ids(result)}"
    )

    # --------------------------------------------------
    # Phase 15
    # Invalid operator
    # --------------------------------------------------

    try:
        entity_manager.query_entities(
            filters={
                "length_mm": {
                    "between": 1200.0,
                }
            }
        )

    except ValueError as error:
        print(
            "\nPhase 15 - Unsupported operator correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Unsupported query operator was accepted."
        )

    # --------------------------------------------------
    # Phase 16
    # Multiple operators for one field rejected
    # --------------------------------------------------

    try:
        entity_manager.query_entities(
            filters={
                "length_mm": {
                    "gte": 1200.0,
                    "lte": 1600.0,
                }
            }
        )

    except ValueError as error:
        print(
            "\nPhase 16 - Multiple operators correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Multiple comparison operators were accepted."
        )

    # --------------------------------------------------
    # Phase 17
    # Invalid NULL comparison
    # --------------------------------------------------

    try:
        entity_manager.query_entities(
            filters={
                "length_mm": {
                    "gte": None,
                }
            }
        )

    except ValueError as error:
        print(
            "\nPhase 17 - Invalid NULL comparison correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Invalid NULL comparison was accepted."
        )

    # --------------------------------------------------
    # Phase 18
    # Non-indexed field still rejected
    # --------------------------------------------------

    try:
        entity_manager.query_entities(
            filters={
                "species": {
                    "eq": "pine",
                }
            }
        )

    except ValueError as error:
        print(
            "\nPhase 18 - Non-indexed field correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Non-indexed field was accepted."
        )

    # --------------------------------------------------
    # Phase 19
    # Reconstruct manager and repeat query
    # --------------------------------------------------

    del entity_manager

    reconstructed_manager = EntityManager(
        workspace=workspace,
        entry=entry,
        index_schema=index_schema,
    )

    result = reconstructed_manager.query_entities(
        filters={
            "availability_status": "available",
            "length_mm": {
                "gte": 1200.0,
            },
            "width_mm": {
                "gte": 180.0,
            },
            "thickness_mm": {
                "gte": 35.0,
            },
        }
    )

    assert entity_ids(result) == [
        "T000001"
    ]

    print(
        "\nPhase 19 - Comparison query persisted after reconstruction:"
    )
    print(
        f"  {entity_ids(result)}"
    )

    print(
        "\nEntity comparison query test passed."
    )


if __name__ == "__main__":
    main()