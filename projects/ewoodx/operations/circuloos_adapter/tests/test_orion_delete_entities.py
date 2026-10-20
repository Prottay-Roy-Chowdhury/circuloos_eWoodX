"""Delete explicitly identified eWoodX integration test entities."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    CirculoosHTTPError,
    OrionClient,
)

TEST_TENANT = "circuloos_ewoodx_material"

TEST_ENTITY_IDS = [
    (
        "urn:ngsi-ld:EwoodxIntegrationTest:"
        "a2845fe0-51b0-441b-8d8e-404cb27d1ced"
    ),
    (
        "urn:ngsi-ld:ewoodx:phase1-test:"
        "1b5191d0-9a02-4024-aea1-828583c0ee6a"
    ),
]


def main() -> None:

    print()
    print("[CIRCULOOS] Orion Test Entity Cleanup")
    print("-" * 55)

    config = CirculoosConfig.from_partner_file()
    client = CirculoosClient(config=config)
    orion = OrionClient(client=client)

    try:
        print(f"Tenant: {TEST_TENANT}")

        for entity_id in TEST_ENTITY_IDS:

            print()
            print(f"Entity: {entity_id}")

            try:
                entity = orion.get_entity(
                    entity_id=entity_id,
                    tenant=TEST_TENANT,
                )

                print(f"Found entity type: {entity['type']}")

            except CirculoosHTTPError as exc:

                if exc.status_code == 404:
                    print("Already absent from Orion. Skipping.")
                    continue

                raise

            orion.delete_entity(
                entity_id=entity_id,
                tenant=TEST_TENANT,
            )

            print("DELETE request: SUCCESS")

            try:
                orion.get_entity(
                    entity_id=entity_id,
                    tenant=TEST_TENANT,
                )

            except CirculoosHTTPError as exc:

                if exc.status_code == 404:
                    print("Orion deletion: VERIFIED")
                else:
                    raise

            else:
                raise AssertionError(
                    f"Entity still exists in Orion: {entity_id}"
                )

        print()
        print("[CIRCULOOS] Cleanup completed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
