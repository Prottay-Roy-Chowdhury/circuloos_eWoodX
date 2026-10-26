"""Standalone test for CIRCULOOS Wood mapping."""

from pathlib import Path
import sys
import json

# Allow execution directly from the repository.
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPOSITORY_ROOT))

from projects.ewoodx.operations.circuloos_adapter.entity_registry import (
    CirculoosEntityRegistry,
)

from projects.ewoodx.operations.circuloos_adapter.wood_mapper import (
    CirculoosWoodMapper,
)

from projects.ewoodx.operations.circuloos_adapter.tests.test_entity_registry import (
    WORKSPACE_NAME,
    TIMBER_ID,
    load_entity_manager,
)


def main():

    entity_manager = load_entity_manager(
        WORKSPACE_NAME
    )

    registry = CirculoosEntityRegistry(
        entity_manager=entity_manager
    )

    mapper = CirculoosWoodMapper(
        entity_manager=entity_manager,
        registry=registry,
        include_thickness=False,
        include_context=False,
    )

    payload = mapper.build(TIMBER_ID)

    assert isinstance(payload, list)
    assert len(payload) == 1

    wood = payload[0]

    assert wood["type"] == "wood"
    assert wood["id"] == registry.load(TIMBER_ID)["wood"]["urn"]

    if "length" in wood:
        assert wood["length"]["unitCode"] == "MMT"

    if "width" in wood:
        assert wood["width"]["unitCode"] == "MMT"

    if "quantity" in wood:
        assert wood["quantity"]["unitCode"] == "MTK"

    output_path = mapper.save(TIMBER_ID)

    saved_payload = json.loads(
        output_path.read_text(encoding="utf-8")
    )

    assert saved_payload == payload

    print("\nSaved Wood payload:", output_path)
    print("Wood mapping test: PASS")


if __name__ == "__main__":
    main()
