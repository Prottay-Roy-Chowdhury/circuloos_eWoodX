"""Check Mintaka temporal records after Orion entity deletion."""

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    CirculoosHTTPError,
    MintakaClient,
)

TEST_TENANT = "circuloos_ewoodx_material"

TEST_ENTITY_IDS = [
    "urn:ngsi-ld:EwoodxIntegrationTest:"
    "a2845fe0-51b0-441b-8d8e-404cb27d1ced",

    "urn:ngsi-ld:ewoodx:phase1-test:"
    "1b5191d0-9a02-4024-aea1-828583c0ee6a",
]


def main():
    config = CirculoosConfig.from_partner_file()
    client = CirculoosClient(config=config)
    mintaka = MintakaClient(client=client)

    try:
        for entity_id in TEST_ENTITY_IDS:
            print()
            print("=" * 60)
            print("Entity:", entity_id)

            try:
                temporal = mintaka.get_temporal_entity(
                    entity_id=entity_id,
                    tenant=TEST_TENANT,
                    last_n=10,
                )

                print(json.dumps(temporal, indent=2))

                attributes = [
                    key for key in temporal
                    if key not in ("id", "type", "@context")
                ]

                if attributes:
                    print("Historical attributes still available.")
                else:
                    print("No historical attributes returned.")

            except CirculoosHTTPError as exc:
                if exc.status_code == 404:
                    print("Temporal entity not found (HTTP 404).")
                else:
                    raise

    finally:
        client.close()


if __name__ == "__main__":
    main()