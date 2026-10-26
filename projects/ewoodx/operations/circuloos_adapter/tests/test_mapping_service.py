
"""End-to-end offline test for CIRCULOOS mapping service.

Starts from an existing eWoodX timber entity.

Workflow:
1. Create or reuse CIRCULOOS registry.
2. Generate Wood payload.
3. Create first RAMP advertisement if none exists.
4. Regenerate existing advertisement.
5. Inspect and verify all mappings.

No CIRCULOOS network requests or publication.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPOSITORY_ROOT))

from projects.ewoodx.operations.circuloos_adapter.mapping_service import (
    CirculoosMappingService,
)

from projects.ewoodx.operations.circuloos_adapter.ramp_mapper import (
    RampAdDetails,
)

from projects.ewoodx.operations.circuloos_adapter.tests.test_entity_registry import (
    WORKSPACE_NAME,
    TIMBER_ID,
    load_entity_manager,
)


def main():

    # ----------------------------------------------------------
    # 1. Initialize service
    # ----------------------------------------------------------

    entity_manager = load_entity_manager(
        WORKSPACE_NAME
    )

    service = CirculoosMappingService(
        entity_manager=entity_manager,
        include_thickness=False,
        include_context=False,
    )

    registry = service.registry

    print("\n========================================")
    print("CIRCULOOS MAPPING SERVICE TEST")
    print("========================================")

    print("Workspace:", WORKSPACE_NAME)
    print("Timber:", TIMBER_ID)

    # ----------------------------------------------------------
    # 2. Prepare Wood (automatically ensures registry)
    # ----------------------------------------------------------

    wood_result = service.prepare_wood(
        TIMBER_ID
    )

    registry_data = registry.load(
        TIMBER_ID
    )

    assert registry_data is not None

    wood_urn = registry_data["wood"]["urn"]

    assert wood_result["wood_urn"] == wood_urn

    wood_path = wood_result["payload_path"]

    assert wood_path.is_file()

    wood_payload = json.loads(
        wood_path.read_text(encoding="utf-8")
    )

    assert isinstance(wood_payload, list)
    assert len(wood_payload) == 1
    assert wood_payload[0]["id"] == wood_urn
    assert wood_payload[0]["type"] == "wood"

    print("\n[1] Registry + Wood mapping: PASS")
    print("Registry:", registry.registry_path(TIMBER_ID))
    print("Wood URN:", wood_urn)
    print("Wood JSON:", wood_path)

    # ----------------------------------------------------------
    # 3. Prepare advertisement details
    # ----------------------------------------------------------

    details = RampAdDetails(
        title="[TEST] eWoodX reclaimed timber",
        description=(
            "Offline mapping service test for "
            f"timber {TIMBER_ID}."
        ),
        material_type_l0="TEST-L0",
        material_type_l1="TEST-L1",
        material_to_sell_or_buy="TEST-MATERIAL",
        available_from="2026-10-26",
        price=0.0,
        image_url="",
    )

    # ----------------------------------------------------------
    # 4. Create first advertisement, or reuse existing AD-001
    # ----------------------------------------------------------

    registry_data = registry.load(
        TIMBER_ID
    )

    existing_ad = next(
        (
            ad
            for ad in registry_data["advertisements"]
            if ad["sequence"] == 1
        ),
        None,
    )

    if existing_ad is None:

        print("\nNo AD-001 found. Creating advertisement.")

        ad_result = service.create_advertisement(
            timber_id=TIMBER_ID,
            details=details,
        )

        assert ad_result["is_new"] is True

    else:

        print("\nAD-001 already exists. Reusing identity.")

        ad_result = service.update_advertisement(
            timber_id=TIMBER_ID,
            sequence=1,
            details=details,
        )

        assert ad_result["is_new"] is False

    assert ad_result["sequence"] == 1

    advertisement_urn = ad_result["advertisement_urn"]

    ad_path = ad_result["payload_path"]

    assert ad_path.is_file()

    ad_payload = json.loads(
        ad_path.read_text(encoding="utf-8")
    )

    assert isinstance(ad_payload, list)
    assert len(ad_payload) == 1

    ad = ad_payload[0]

    assert ad["id"] == advertisement_urn
    assert ad["type"] == "others"

    assert ad["refMaterial"] == {
        "type": "Relationship",
        "object": wood_urn,
    }

    assert (
        ad["materialQuantity"]["value"]
        == wood_payload[0]["quantity"]["value"]
    )

    assert (
        ad["materialQuantity"]["unitCode"]
        == "MTK"
    )

    print("\n[2] Advertisement creation/reuse: PASS")
    print("Advertisement URN:", advertisement_urn)
    print("Advertisement JSON:", ad_path)

    # ----------------------------------------------------------
    # 5. Update existing advertisement
    # ----------------------------------------------------------

    registry_before_update = registry.load(
        TIMBER_ID
    )

    updated_details = RampAdDetails(
        title="[TEST] Updated eWoodX reclaimed timber",
        description=(
            "Updated local advertisement for "
            f"timber {TIMBER_ID}."
        ),
        material_type_l0="TEST-L0",
        material_type_l1="TEST-L1",
        material_to_sell_or_buy="TEST-MATERIAL",
        available_from="2026-10-26",
        price=0.0,
        image_url="",
    )

    update_result = service.update_advertisement(
        timber_id=TIMBER_ID,
        sequence=1,
        details=updated_details,
    )

    assert update_result["is_new"] is False

    assert (
        update_result["advertisement_urn"]
        == advertisement_urn
    )

    updated_payload = json.loads(
        update_result["payload_path"].read_text(
            encoding="utf-8"
        )
    )

    assert (
        updated_payload[0]["materialAdTitle"]["value"]
        == updated_details.title
    )

    registry_after_update = registry.load(
        TIMBER_ID
    )

    assert (
        registry_after_update
        == registry_before_update
    )

    print("\n[3] Existing advertisement update: PASS")
    print("Advertisement URN unchanged: PASS")
    print("Registry unchanged during update: PASS")

    # ----------------------------------------------------------
    # 6. Inspect mappings
    # ----------------------------------------------------------

    registry_before_inspection = registry.load(
        TIMBER_ID
    )

    mapping = service.get_mapping(
        TIMBER_ID
    )

    assert mapping is not None

    assert mapping["timber_id"] == TIMBER_ID

    assert mapping["wood"]["urn"] == wood_urn

    assert mapping["wood"]["payload_path"] == wood_path

    assert mapping["registry_path"].is_file()

    mapped_ad = next(
        (
            ad
            for ad in mapping["advertisements"]
            if ad["sequence"] == 1
        ),
        None,
    )

    assert mapped_ad is not None

    assert mapped_ad["urn"] == advertisement_urn
    assert mapped_ad["payload_path"] == ad_path

    assert (
        registry.load(TIMBER_ID)
        == registry_before_inspection
    )

    print("\n[4] Mapping inspection: PASS")

    # ----------------------------------------------------------
    # 7. Verify persistent registry consistency
    # ----------------------------------------------------------

    final_registry = registry.load(
        TIMBER_ID
    )

    assert (
        final_registry["wood"]["urn"]
        == wood_urn
    )

    assert (
        final_registry["wood"]["status"]
        == "local_only"
    )

    assert len(final_registry["advertisements"]) >= 1

    final_ad = next(
        ad
        for ad in final_registry["advertisements"]
        if ad["sequence"] == 1
    )

    assert final_ad["urn"] == advertisement_urn

    assert final_ad["ref_material"] == wood_urn

    assert final_ad["status"] == "local_only"

    print("\n[5] Registry consistency: PASS")

    # ----------------------------------------------------------
    # 8. Final output
    # ----------------------------------------------------------

    print("\n========================================")
    print("GENERATED CIRCULOOS FILES")
    print("========================================")

    print("Registry:", registry.registry_path(TIMBER_ID))
    print("Wood:", wood_path)
    print("Advertisement:", ad_path)

    print("\nWood URN:", wood_urn)
    print("Advertisement URN:", advertisement_urn)

    print("\n========================================")
    print("MAPPING SERVICE TEST: PASS")
    print("========================================")


if __name__ == "__main__":
    main()
