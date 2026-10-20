"""Test updating and creating RAMP-compatible material entities."""

from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.ewoodx.operations.circuloos_adapter import (
    CirculoosConfig,
    CirculoosClient,
    OrionClient,
)

TENANT = "circuloos_ewoodx_material"

EXISTING_ID = (
    "urn:ngsi-ld:others:"
    "54b8895d-774d-41ee-91b0-01af0ef77dd0"
)

NEW_ID = "urn:ngsi-ld:others:ewoodx-ramp-test-001"

APPLY_CHANGES = True  # Set to False to preview changes without modifying entities.

OUTPUT_DIR = Path(__file__).resolve().parent / "ramp_test_data"


def timestamp():
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def set_property(entity, name, value, observed_at):
    entity[name] = {
        "type": "Property",
        "value": value,
        "observedAt": observed_at,
    }


def prepare_entities(original):
    now = timestamp()

    updated = deepcopy(original)
    created = deepcopy(original)

    # Update existing material.
    set_property(
        updated,
        "materialAdTitle",
        "flooring wood panels - eWoodX update test",
        now,
    )
    set_property(
        updated,
        "materialDescription",
        "Existing RAMP material updated through the "
        "eWoodX CIRCULOOS adapter.",
        now,
    )

    # Create a second material.
    created["id"] = NEW_ID

    set_property(
        created,
        "materialAdTitle",
        "eWoodX reclaimed wood panels - new test",
        now,
    )
    set_property(
        created,
        "materialDescription",
        "New test material created through the "
        "eWoodX CIRCULOOS adapter.",
        now,
    )

    # Give the new entity fresh observation timestamps.
    for key, attribute in created.items():
        if isinstance(attribute, dict) and "observedAt" in attribute:
            attribute["observedAt"] = now

    # The official CIRCULOOS upsert examples omit
    # entity-level @context from the JSON body.
    updated.pop("@context", None)
    created.pop("@context", None)

    return updated, created


def main():
    config = CirculoosConfig.from_partner_file()
    client = CirculoosClient(config=config)
    orion = OrionClient(client=client)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        original = orion.get_entity(
            entity_id=EXISTING_ID,
            tenant=TENANT,
        )

        backup_path = OUTPUT_DIR / "original_material_backup.json"

        # Do not overwrite an earlier backup.
        if not backup_path.exists():
            backup_path.write_text(
                json.dumps(original, indent=2),
                encoding="utf-8",
            )

        updated, created = prepare_entities(original)

        (OUTPUT_DIR / "updated_material.json").write_text(
            json.dumps([updated], indent=2),
            encoding="utf-8",
        )

        (OUTPUT_DIR / "new_material.json").write_text(
            json.dumps([created], indent=2),
            encoding="utf-8",
        )

        print()
        print("[CIRCULOOS] RAMP Material Integration Test")
        print("=" * 60)
        print("Tenant:", TENANT)
        print("Existing ID:", EXISTING_ID)
        print("New ID:", NEW_ID)
        print("Backup:", backup_path)
        print("Apply changes:", APPLY_CHANGES)

        if not APPLY_CHANGES:
            print()
            print("PREVIEW ONLY - no entities modified.")
            print("Inspect the generated JSON files first.")
            return

        # Upsert existing material.
        orion.upsert_entities(
            [updated],
            tenant=TENANT,
        )
        print()
        print("Existing material upsert: SUCCESS")

        # Upsert new material.
        orion.upsert_entities(
            [created],
            tenant=TENANT,
        )
        print("New material upsert: SUCCESS")

        # Verify both entities.
        for entity_id in (EXISTING_ID, NEW_ID):
            result = orion.get_entity(
                entity_id=entity_id,
                tenant=TENANT,
            )

            print()
            print("Verified ID:", result["id"])
            print("Type:", result["type"])
            print(
                "Title:",
                result["materialAdTitle"]["value"],
            )

    finally:
        client.close()


if __name__ == "__main__":
    main()