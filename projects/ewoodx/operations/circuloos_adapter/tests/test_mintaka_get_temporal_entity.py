"""Test Mintaka temporal history retrieval."""

from pathlib import Path
import json
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))


from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    MintakaClient,
    CirculoosHTTPError,
)


TEST_TENANT = "circuloos_ewoodx_material"

TEST_ENTITY_ID = (
    "urn:ngsi-ld:EwoodxIntegrationTest:"
    "a2845fe0-51b0-441b-8d8e-404cb27d1ced"
)

TEST_CONTEXT = None
LAST_N = 10


def main() -> None:

    print()
    print("[CIRCULOOS] Mintaka Temporal Entity Test")
    print("-" * 50)

    config = CirculoosConfig.from_partner_file()
    client = CirculoosClient(config=config)
    mintaka = MintakaClient(client=client)

    try:
        print(f"Tenant: {TEST_TENANT}")
        print(f"Entity ID: {TEST_ENTITY_ID}")
        print(f"Context: {TEST_CONTEXT}")
        print(f"Last N: {LAST_N}")

        print()
        print("[TEST 1] Retrieve Temporal Entity")

        try:
            history = mintaka.get_temporal_entity(
                entity_id=TEST_ENTITY_ID,
                tenant=TEST_TENANT,
                context=TEST_CONTEXT,
                last_n=LAST_N,
            )

        except CirculoosHTTPError as exc:
            print(f"Mintaka request failed: {exc}")
            raise

        print()
        print("[TEMPORAL RESPONSE]")
        print(json.dumps(history, indent=2))

        assert isinstance(history, dict), (
            "Expected a temporal entity dictionary."
        )

        assert history.get("id") == TEST_ENTITY_ID, (
            "Returned entity ID does not match."
        )

        print()
        print("[RESPONSE ANALYSIS]")
        print(f"Type: {history.get('type')}")

        for attribute, values in history.items():

            if attribute in ("id", "type", "@context"):
                continue

            print()
            print(f"Attribute: {attribute}")

            if isinstance(values, list):

                print(f"Instances returned: {len(values)}")

                for index, instance in enumerate(values, 1):
                    print(f"  Instance {index}:")
                    print(f"    Value: {instance.get('value')}")
                    print(
                        "    ObservedAt: "
                        f"{instance.get('observedAt')}"
                    )

            else:
                print(f"  Unexpected format: {type(values)}")

        print()
        print("[CIRCULOOS] Mintaka retrieval: SUCCESS")

    finally:
        client.close()


if __name__ == "__main__":
    main()
