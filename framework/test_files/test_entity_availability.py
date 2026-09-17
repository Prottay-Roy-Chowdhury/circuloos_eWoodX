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
    / "entity_availability_test_project"
)


def read_manifest(entity):
    with entity.manifest.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def read_database_state(
    database_path,
    entity_id,
):
    with sqlite3.connect(
        database_path
    ) as connection:
        return connection.execute(
            """
            SELECT
                availability_status,
                claimed_by
            FROM entities
            WHERE entity_id = ?
            """,
            (entity_id,),
        ).fetchone()


def assert_state(
    entity,
    database_path,
    expected_status,
    expected_claimed_by,
):
    """
    Verify that entity.json and SQLite agree.
    """

    manifest_data = read_manifest(
        entity
    )

    database_state = read_database_state(
        database_path,
        entity.entity_id,
    )

    assert database_state is not None

    database_status, database_claimed_by = (
        database_state
    )

    assert (
        manifest_data["availability_status"]
        == expected_status
    )

    assert (
        manifest_data["claimed_by"]
        == expected_claimed_by
    )

    assert (
        database_status
        == expected_status
    )

    assert (
        database_claimed_by
        == expected_claimed_by
    )


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
        "thickness_mm": "REAL",
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
        f"  Entry:     {entry.root}"
    )
    print(
        f"  Database:  {entity_manager.database_path}"
    )

    # --------------------------------------------------
    # Phase 2
    # Create entity
    # --------------------------------------------------

    entity = entity_manager.create_entity(
        entity_id="T000001",
        entity_type="timber",
        metadata={
            "color": "brown",
            "length_mm": 1200.0,
            "thickness_mm": 35.0,
            "species": "pine",
        },
    )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="available",
        expected_claimed_by=None,
    )

    print(
        "\nPhase 2 - New entity is available:"
    )
    print(
        "  T000001 -> available"
    )

    # --------------------------------------------------
    # Phase 3
    # Consumer A claims entity
    # --------------------------------------------------

    entity_manager.claim_entity(
        entity_id="T000001",
        claimed_by="design_agent_A",
    )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="claimed",
        expected_claimed_by="design_agent_A",
    )

    print(
        "\nPhase 3 - Entity claimed:"
    )
    print(
        "  T000001 -> claimed by design_agent_A"
    )

    # --------------------------------------------------
    # Phase 4
    # Consumer B cannot claim it
    # --------------------------------------------------

    try:
        entity_manager.claim_entity(
            entity_id="T000001",
            claimed_by="design_agent_B",
        )

    except RuntimeError as error:
        print(
            "\nPhase 4 - Second claim correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Second consumer was incorrectly "
            "allowed to claim the entity."
        )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="claimed",
        expected_claimed_by="design_agent_A",
    )

    # --------------------------------------------------
    # Phase 5
    # Wrong consumer cannot release
    # --------------------------------------------------

    try:
        entity_manager.release_entity(
            entity_id="T000001",
            claimed_by="design_agent_B",
        )

    except RuntimeError as error:
        print(
            "\nPhase 5 - Wrong-owner release correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Wrong consumer was incorrectly "
            "allowed to release the entity."
        )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="claimed",
        expected_claimed_by="design_agent_A",
    )

    # --------------------------------------------------
    # Phase 6
    # Correct consumer releases
    # --------------------------------------------------

    entity_manager.release_entity(
        entity_id="T000001",
        claimed_by="design_agent_A",
    )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="available",
        expected_claimed_by=None,
    )

    print(
        "\nPhase 6 - Entity released:"
    )
    print(
        "  T000001 -> available"
    )

    # --------------------------------------------------
    # Phase 7
    # Consumer B can now claim it
    # --------------------------------------------------

    entity_manager.claim_entity(
        entity_id="T000001",
        claimed_by="design_agent_B",
    )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="claimed",
        expected_claimed_by="design_agent_B",
    )

    print(
        "\nPhase 7 - Entity re-claimed:"
    )
    print(
        "  T000001 -> claimed by design_agent_B"
    )

    # --------------------------------------------------
    # Phase 8
    # Wrong consumer cannot finalize it
    # --------------------------------------------------

    try:
        entity_manager.mark_unavailable(
            entity_id="T000001",
            claimed_by="design_agent_A",
        )

    except RuntimeError as error:
        print(
            "\nPhase 8 - Wrong-owner finalization correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Wrong consumer was incorrectly "
            "allowed to finalize the entity."
        )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="claimed",
        expected_claimed_by="design_agent_B",
    )

    # --------------------------------------------------
    # Phase 9
    # Correct consumer finalizes it
    # --------------------------------------------------

    entity_manager.mark_unavailable(
        entity_id="T000001",
        claimed_by="design_agent_B",
    )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="unavailable",
        expected_claimed_by=None,
    )

    print(
        "\nPhase 9 - Entity finalized:"
    )
    print(
        "  T000001 -> unavailable"
    )

    # --------------------------------------------------
    # Phase 10
    # Unavailable entity cannot be claimed
    # --------------------------------------------------

    try:
        entity_manager.claim_entity(
            entity_id="T000001",
            claimed_by="design_agent_A",
        )

    except RuntimeError as error:
        print(
            "\nPhase 10 - Claim of unavailable entity correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Unavailable entity was incorrectly "
            "allowed to be claimed."
        )

    # --------------------------------------------------
    # Phase 11
    # Manual simulation reset
    # --------------------------------------------------

    entity_manager.set_availability(
        entity_id="T000001",
        availability_status="available",
    )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="available",
        expected_claimed_by=None,
    )

    print(
        "\nPhase 11 - Manual reset:"
    )
    print(
        "  T000001 -> available"
    )

    # --------------------------------------------------
    # Phase 12
    # Claim after manual reset
    # --------------------------------------------------

    entity_manager.claim_entity(
        entity_id="T000001",
        claimed_by="simulation_agent",
    )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="claimed",
        expected_claimed_by="simulation_agent",
    )

    print(
        "\nPhase 12 - Claim after manual reset:"
    )
    print(
        "  T000001 -> claimed by simulation_agent"
    )

    # Release before manual status control
    entity_manager.release_entity(
        entity_id="T000001",
        claimed_by="simulation_agent",
    )

    # --------------------------------------------------
    # Phase 13
    # Manual unavailable
    # --------------------------------------------------

    entity_manager.set_availability(
        entity_id="T000001",
        availability_status="unavailable",
    )

    assert_state(
        entity=entity,
        database_path=entity_manager.database_path,
        expected_status="unavailable",
        expected_claimed_by=None,
    )

    print(
        "\nPhase 13 - Manual unavailable:"
    )
    print(
        "  T000001 -> unavailable"
    )

    # --------------------------------------------------
    # Phase 14
    # Manual claimed state must be rejected
    # --------------------------------------------------

    try:
        entity_manager.set_availability(
            entity_id="T000001",
            availability_status="claimed",
        )

    except ValueError as error:
        print(
            "\nPhase 14 - Manual claimed state correctly rejected:"
        )
        print(
            f"  {error}"
        )

    else:
        raise AssertionError(
            "Manual control was incorrectly "
            "allowed to create a claimed state."
        )

    # --------------------------------------------------
    # Phase 15
    # Query availability through generic query API
    # --------------------------------------------------

    unavailable = (
        entity_manager.query_entities(
            filters={
                "entity_type": "timber",
                "availability_status": "unavailable",
            }
        )
    )

    unavailable_ids = [
        item.entity_id
        for item in unavailable
    ]

    assert unavailable_ids == [
        "T000001"
    ]

    print(
        "\nPhase 15 - Availability query:"
    )
    print(
        f"  {unavailable_ids}"
    )

    # --------------------------------------------------
    # Phase 16
    # Reconstruct manager
    # --------------------------------------------------

    del entity_manager

    reconstructed_manager = EntityManager(
        workspace=workspace,
        entry=entry,
        index_schema=index_schema,
    )

    reconstructed_entity = (
        reconstructed_manager.load_entity(
            "T000001"
        )
    )

    assert_state(
        entity=reconstructed_entity,
        database_path=reconstructed_manager.database_path,
        expected_status="unavailable",
        expected_claimed_by=None,
    )

    print(
        "\nPhase 16 - State persisted after manager reconstruction:"
    )
    print(
        "  T000001 -> unavailable"
    )

    print(
        "\nEntity availability lifecycle test passed."
    )


if __name__ == "__main__":
    main()