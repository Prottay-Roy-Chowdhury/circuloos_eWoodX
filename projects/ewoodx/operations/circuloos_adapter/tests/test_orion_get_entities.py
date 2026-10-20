"""Test CIRCULOOS Orion-LD entity queries."""

from pathlib import Path
import sys


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
TEST_ENTITY_TYPE = "ProductionFacility"
TEST_CONTEXT = None
TEST_LIMIT = 100


def main() -> None:

    print()
    print("[CIRCULOOS] Orion-LD Get Entities Test")
    print("-" * 50)

    config = CirculoosConfig.from_partner_file()

    client = CirculoosClient(
        config=config,
    )

    orion = OrionClient(
        client=client,
    )

    try:

        # --------------------------------------------------
        # Test 1: Retrieve entities without type filter
        # --------------------------------------------------

        print()
        print("[TEST 1] Retrieve All Entities")

        entities = orion.get_entities(
            tenant=TEST_TENANT,
            context=TEST_CONTEXT,
            limit=TEST_LIMIT,
        )

        assert isinstance(entities, list)

        print(f"Entities returned: {len(entities)}")

        for entity in entities:
            print(
                f"  ID: {entity.get('id')}"
            )
            print(
                f"  Type: {entity.get('type')}"
            )

        print("Unfiltered entity query: SUCCESS")

        # --------------------------------------------------
        # Test 2: Retrieve entities by type
        # --------------------------------------------------

        print()
        print("[TEST 2] Retrieve Entities by Type")

        filtered_entities = orion.get_entities(
            tenant=TEST_TENANT,
            entity_type=TEST_ENTITY_TYPE,
            context=TEST_CONTEXT,
            limit=TEST_LIMIT,
        )

        assert isinstance(filtered_entities, list)

        print(f"Requested type: {TEST_ENTITY_TYPE}")
        print(f"Entities returned: {len(filtered_entities)}")

        for entity in filtered_entities:

            print(f"  ID: {entity.get('id')}")
            print(f"  Type: {entity.get('type')}")

            assert entity.get("type") == TEST_ENTITY_TYPE, (
                "Returned entity type does not match."
            )

        print("Filtered entity query: SUCCESS")

        # --------------------------------------------------
        # Summary
        # --------------------------------------------------

        print()
        print("[CIRCULOOS] Orion-LD entity query tests passed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
