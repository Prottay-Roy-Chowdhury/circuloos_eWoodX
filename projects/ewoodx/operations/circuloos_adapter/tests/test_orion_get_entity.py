"""Test CIRCULOOS Orion-LD single entity retrieval."""

from pathlib import Path
import sys
import json


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

TEST_ENTITY_ID = (
    "urn:ngsi-ld:productionFacility:initial_test_material:"
    "6c0b8d78-9158-418a-aef8-c259cd68b972"
)


def main() -> None:

    print()
    print("[CIRCULOOS] Orion-LD Get Entity Test")
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
        # Retrieve entity without explicit JSON-LD context
        # --------------------------------------------------

        print()
        print(f"Tenant: {TEST_TENANT}")
        print(f"Entity ID: {TEST_ENTITY_ID}")
        print("Context: None")
        print("Accept: application/ld+json")

        entity = orion.get_entity(
            entity_id=TEST_ENTITY_ID,
            tenant=TEST_TENANT,
            context=None,
        )

        # --------------------------------------------------
        # Validate response
        # --------------------------------------------------

        assert isinstance(entity, dict), (
            "Expected a JSON object."
        )

        assert entity.get("id") == TEST_ENTITY_ID, (
            "Returned entity ID does not match."
        )

        print()
        print("[ENTITY RESPONSE]")

        print(
            json.dumps(
                entity,
                indent=2,
                ensure_ascii=False,
            )
        )

        print()
        print("[RESPONSE ANALYSIS]")
        print(f"Type: {entity.get('type')}")
        print(f"Contains @context: {'@context' in entity}")
        print(f"Attributes: {list(entity.keys())}")

        print()
        print("Single entity retrieval: SUCCESS")
        print("[CIRCULOOS] Orion-LD get entity test passed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
