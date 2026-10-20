"""Inspect existing material entities in the eWoodX RAMP tenant."""

from pathlib import Path
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


def main():
    config = CirculoosConfig.from_partner_file()
    client = CirculoosClient(config=config)
    orion = OrionClient(client=client)

    try:
        entities = orion.get_entities(
            tenant=TENANT,
            limit=100,
        )

        print()
        print("[CIRCULOOS] Existing Tenant Entities")
        print("=" * 60)

        for entity in entities:
            print()
            print("ID:", entity.get("id"))
            print("Type:", entity.get("type"))

            if "materialAdTitle" in entity:
                print(
                    "Material title:",
                    entity["materialAdTitle"].get("value")
                )

        print()
        print("[MATERIAL ENTITIES]")
        print("=" * 60)

        materials = [
            entity
            for entity in entities
            if "materialAdTitle" in entity
        ]

        for material in materials:
            print(json.dumps(material, indent=2))

        print()
        print(f"Material entities found: {len(materials)}")

    finally:
        client.close()


if __name__ == "__main__":
    main()