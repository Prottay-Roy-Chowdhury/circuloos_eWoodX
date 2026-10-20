"""Test CIRCULOOS Orion-LD entity ID retrieval."""

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

TEST_ID_PATTERN = "urn:ngsi-ld:.*"

TEST_LIMIT = 1000


def main() -> None:

    print()
    print("[CIRCULOOS] Orion-LD Entity ID Test")
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
        # Retrieve entity IDs
        # --------------------------------------------------

        print()
        print(f"Tenant: {TEST_TENANT}")
        print(f"ID pattern: {TEST_ID_PATTERN}")
        print(f"Limit: {TEST_LIMIT}")

        entity_ids = orion.get_entity_ids(
            tenant=TEST_TENANT,
            id_pattern=TEST_ID_PATTERN,
            limit=TEST_LIMIT,
        )

        # --------------------------------------------------
        # Validate response
        # --------------------------------------------------

        assert isinstance(entity_ids, list), (
            "Expected a list of entity IDs."
        )

        assert all(
            isinstance(entity_id, str)
            for entity_id in entity_ids
        ), "All entity IDs must be strings."

        print()
        print(f"Entities found: {len(entity_ids)}")

        for index, entity_id in enumerate(
            entity_ids,
            start=1,
        ):
            print(f"  [{index}] {entity_id}")

        print()
        print("Entity ID retrieval: SUCCESS")

        print()
        print("[CIRCULOOS] Orion-LD test passed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
