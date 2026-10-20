"""Test multiple temporal observations through Orion-LD and Mintaka."""

from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    OrionClient,
    MintakaClient,
)


# --------------------------------------------------
# Test configuration
# --------------------------------------------------

TEST_TENANT = "circuloos_ewoodx_material"

TEST_ENTITY_ID = (
    "urn:ngsi-ld:ewoodx:phase1-test:"
    "1b5191d0-9a02-4024-aea1-828583c0ee6a"
)

TEST_CONTEXT = None

VALUES = [
    "EWOODX-PHASE1-UPDATE-1",
    "EWOODX-PHASE1-UPDATE-2",
]


def utc_timestamp(dt: datetime) -> str:
    return dt.isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def make_entity(
    entity_id: str,
    value: str,
    observed_at: str,
) -> dict:

    return {
        "id": entity_id,
        "type": "integration",
        "magic-number": {
            "type": "Property",
            "value": value,
            "observedAt": observed_at,
        },
    }


def main() -> None:

    print()
    print("[CIRCULOOS] Mintaka Multiple Observations Test")
    print("-" * 55)

    config = CirculoosConfig.from_partner_file()
    client = CirculoosClient(config=config)

    orion = OrionClient(client=client)
    mintaka = MintakaClient(client=client)

    # Use two different timestamps.
    base_time = datetime.now(timezone.utc)

    try:

        print(f"Tenant: {TEST_TENANT}")
        print(f"Entity ID: {TEST_ENTITY_ID}")

        # --------------------------------------------------
        # Test 1: Submit sequential updates
        # --------------------------------------------------

        print()
        print("[TEST 1] Submit Temporal Updates")

        for index, value in enumerate(VALUES, start=1):

            observed_at = utc_timestamp(
                base_time + timedelta(seconds=index)
            )

            entity = make_entity(
                entity_id=TEST_ENTITY_ID,
                value=value,
                observed_at=observed_at,
            )

            orion.upsert_entities(
                entities=[entity],
                tenant=TEST_TENANT,
                context=TEST_CONTEXT,
            )

            print()
            print(f"Update {index}: SUCCESS")
            print(f"Value: {value}")
            print(f"ObservedAt: {observed_at}")

        # --------------------------------------------------
        # Test 2: Verify current Orion state
        # --------------------------------------------------

        print()
        print("[TEST 2] Verify Orion Current State")

        current = orion.get_entity(
            entity_id=TEST_ENTITY_ID,
            tenant=TEST_TENANT,
        )

        print(json.dumps(current, indent=2))

        assert (
            current["magic-number"]["value"]
            == VALUES[-1]
        )

        print("Current Orion value: VERIFIED")

        # --------------------------------------------------
        # Test 3: Retrieve Mintaka history
        # --------------------------------------------------

        print()
        print("[TEST 3] Retrieve Mintaka History")

        temporal = mintaka.get_temporal_entity(
            entity_id=TEST_ENTITY_ID,
            tenant=TEST_TENANT,
            context=TEST_CONTEXT,
            last_n=10,
        )

        print(json.dumps(temporal, indent=2))

        # --------------------------------------------------
        # Analyze temporal instances
        # --------------------------------------------------

        print()
        print("[RESPONSE ANALYSIS]")

        attribute = temporal.get("magic-number")

        if attribute is None:
            print("No temporal attribute returned.")

        else:

            instances = (
                attribute
                if isinstance(attribute, list)
                else [attribute]
            )

            print(
                f"Temporal instances returned: {len(instances)}"
            )

            for index, instance in enumerate(instances, 1):

                print()
                print(f"Instance {index}")
                print(f"Value: {instance.get('value')}")
                print(
                    f"ObservedAt: {instance.get('observedAt')}"
                )
                print(
                    f"InstanceId: {instance.get('instanceId')}"
                )

            values_found = [
                instance.get("value")
                for instance in instances
            ]

            print()
            print("Values found:", values_found)

            expected_values = [
                "EWOODX-PHASE1-TEST",
                *VALUES,
            ]

            missing_values = [
                value
                for value in expected_values
                if value not in values_found
            ]

            if not missing_values:
                print("All three observations: VERIFIED")
            else:
                print(
                    "Observations not returned:",
                    missing_values,
                )

        print()
        print("[CIRCULOOS] Multiple observations test completed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()