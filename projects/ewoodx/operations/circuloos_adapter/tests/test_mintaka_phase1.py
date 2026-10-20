"""Test Mintaka using the official CIRCULOOS Phase 1 payload pattern."""

from pathlib import Path
from datetime import datetime, timezone
import json
import sys
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    OrionClient,
    MintakaClient,
)

TEST_TENANT = "circuloos_ewoodx_material"
TEST_CONTEXT = None


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def main() -> None:

    print()
    print("[CIRCULOOS] Mintaka Phase 1 Reference Test")
    print("-" * 55)

    config = CirculoosConfig.from_partner_file()
    client = CirculoosClient(config=config)

    orion = OrionClient(client=client)
    mintaka = MintakaClient(client=client)

    entity_id = (
        "urn:ngsi-ld:ewoodx:phase1-test:"
        f"{uuid.uuid4()}"
    )

    observed_at = utc_timestamp()

    entity = {
        "id": entity_id,
        "type": "integration",
        "magic-number": {
            "type": "Property",
            "value": "EWOODX-PHASE1-TEST",
            "observedAt": observed_at,
        },
    }

    try:
        print(f"Tenant: {TEST_TENANT}")
        print(f"Entity ID: {entity_id}")
        print(f"ObservedAt: {observed_at}")

        # ----------------------------------------------
        # Test 1: Write Phase 1 entity
        # ----------------------------------------------

        print()
        print("[TEST 1] Write Phase 1 Entity")

        orion.upsert_entities(
            entities=[entity],
            tenant=TEST_TENANT,
            context=TEST_CONTEXT,
        )

        print("Orion upsert: SUCCESS")

        # ----------------------------------------------
        # Test 2: Read current Orion state
        # ----------------------------------------------

        print()
        print("[TEST 2] Read Orion Entity")

        current = orion.get_entity(
            entity_id=entity_id,
            tenant=TEST_TENANT,
        )

        print(json.dumps(current, indent=2))

        assert current["id"] == entity_id

        # ----------------------------------------------
        # Test 3: Read Mintaka temporal state
        # ----------------------------------------------

        print()
        print("[TEST 3] Read Mintaka Temporal Entity")

        temporal = mintaka.get_temporal_entity(
            entity_id=entity_id,
            tenant=TEST_TENANT,
            context=TEST_CONTEXT,
            last_n=10,
        )

        print(json.dumps(temporal, indent=2))

        assert temporal["id"] == entity_id

        # ----------------------------------------------
        # Compare attributes
        # ----------------------------------------------

        print()
        print("[RESPONSE ANALYSIS]")

        current_attributes = [
            key for key in current
            if key not in ("id", "type", "@context")
        ]

        temporal_attributes = [
            key for key in temporal
            if key not in ("id", "type", "@context")
        ]

        print("Orion attributes:", current_attributes)
        print("Mintaka attributes:", temporal_attributes)

        if temporal_attributes:
            print("Temporal attributes found: YES")
        else:
            print("Temporal attributes found: NO")

        print()
        print("[CIRCULOOS] Phase 1 diagnostic completed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()