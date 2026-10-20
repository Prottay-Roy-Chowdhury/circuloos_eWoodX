"""Test CIRCULOOS Orion-LD entity creation and update."""

from pathlib import Path
import sys
import uuid


PROJECT_ROOT = Path(
    __file__
).resolve().parents[5]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    OrionClient,
)


# --------------------------------------------------
# Test configuration
# --------------------------------------------------

TEST_TENANT = "circuloos_ewoodx_material"

TEST_CONTEXT = None


def make_entity(
    entity_id: str,
    value: int,
) -> dict:

    return {
        "id": entity_id,
        "type": "EwoodxIntegrationTest",
        "testValue": {
            "type": "Property",
            "value": value,
        },
    }


def main() -> None:

    print()
    print("[CIRCULOOS] Orion-LD Upsert Test")
    print("-" * 50)

    config = CirculoosConfig.from_partner_file()

    client = CirculoosClient(
        config=config,
    )

    orion = OrionClient(
        client=client,
    )

    entity_id = (
        "urn:ngsi-ld:EwoodxIntegrationTest:"
        f"{uuid.uuid4()}"
    )

    print(f"Tenant: {TEST_TENANT}")
    print(f"Test entity: {entity_id}")

    try:

        # --------------------------------------------------
        # Test 1: Create entity
        # --------------------------------------------------

        print()
        print("[TEST 1] Create Entity")

        orion.upsert_entities(
            entities=[
                make_entity(
                    entity_id=entity_id,
                    value=100,
                )
            ],
            tenant=TEST_TENANT,
            context=TEST_CONTEXT,
        )

        created = orion.get_entity(
            entity_id=entity_id,
            tenant=TEST_TENANT,
        )

        assert created["id"] == entity_id
        assert created["testValue"]["value"] == 100

        print("Entity creation: SUCCESS")
        print("Initial value: 100")

        # --------------------------------------------------
        # Test 2: Update entity
        # --------------------------------------------------

        print()
        print("[TEST 2] Update Entity")

        orion.upsert_entities(
            entities=[
                make_entity(
                    entity_id=entity_id,
                    value=200,
                )
            ],
            tenant=TEST_TENANT,
            context=TEST_CONTEXT,
        )

        updated = orion.get_entity(
            entity_id=entity_id,
            tenant=TEST_TENANT,
        )

        assert updated["id"] == entity_id
        assert updated["testValue"]["value"] == 200

        print("Entity update: SUCCESS")
        print("Updated value: 200")

        print()
        print("[CIRCULOOS] Orion-LD upsert tests passed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
