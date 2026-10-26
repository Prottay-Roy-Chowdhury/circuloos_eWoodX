"""Standalone offline test for CIRCULOOS RAMP advertisement mapping.

Uses:
- Existing workspace and timber entity.
- Existing CIRCULOOS registry.
- Previously allocated advertisement.
- Existing circuloos_wood.json.
- RAMP defaults from circuloos_adapter/config.py.

No network requests or publication.
"""

from pathlib import Path
import sys
import json

# Allow execution directly from the repository.
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPOSITORY_ROOT))

from projects.ewoodx.operations.circuloos_adapter.entity_registry import (
    CirculoosEntityRegistry,
)

from projects.ewoodx.operations.circuloos_adapter.ramp_mapper import (
    CirculoosRampMapper,
    RampAdDetails,
)

from projects.ewoodx.operations.circuloos_adapter.config import (
    RAMP_OWNER_URN,
    RAMP_PRODUCTION_FACILITY_URN,
    RAMP_COUNTRY,
    RAMP_AD_TYPE,
    RAMP_AD_STATUS,
    RAMP_PHYSICAL_FORM,
)

from projects.ewoodx.operations.circuloos_adapter.tests.test_entity_registry import (
    WORKSPACE_NAME,
    TIMBER_ID,
    load_entity_manager,
)


def main():

    # ----------------------------------------------------------
    # 1. Initialize existing workspace and EntityManager
    # ----------------------------------------------------------

    entity_manager = load_entity_manager(
        WORKSPACE_NAME
    )

    registry = CirculoosEntityRegistry(
        entity_manager=entity_manager
    )

    # ----------------------------------------------------------
    # 2. Load existing CIRCULOOS registry
    # ----------------------------------------------------------

    registry_data = registry.load(
        TIMBER_ID
    )

    if registry_data is None:
        raise RuntimeError(
            "CIRCULOOS registry not found. "
            "Run the entity registry test first."
        )

    advertisements = registry_data.get(
        "advertisements",
        []
    )

    if not advertisements:
        raise RuntimeError(
            "No advertisements allocated. "
            "Allocate an advertisement first."
        )

    # Reuse the first allocated advertisement (AD-001).
    advertisement = next(
        (
            ad
            for ad in advertisements
            if ad["sequence"] == 1
        ),
        None,
    )

    if advertisement is None:
        raise RuntimeError(
            "Advertisement AD-001 not found."
        )

    advertisement_urn = advertisement["urn"]
    wood_urn = registry_data["wood"]["urn"]

    print("\nTimber ID:", TIMBER_ID)
    print("Wood URN:", wood_urn)
    print("Advertisement URN:", advertisement_urn)

    # ----------------------------------------------------------
    # 3. Prepare advertisement-specific information
    # ----------------------------------------------------------

    # These values are for an offline mapping test.
    # Replace classification codes with verified RAMP codes
    # before attempting real publication.

    details = RampAdDetails(
        title="[TEST] eWoodX reclaimed timber",
        description=(
            "Offline test advertisement for scanned "
            "reclaimed timber component T-0001-WAR."
        ),

        material_type_l0="TEST-L0",
        material_type_l1="TEST-L1",
        material_to_sell_or_buy="TEST-MATERIAL",

        available_from="2026-10-26",
        price=0.0,
        image_url="",
    )

    # ----------------------------------------------------------
    # 4. Verify configuration defaults
    # ----------------------------------------------------------

    assert details.owner_urn == RAMP_OWNER_URN

    assert (
        details.production_facility_urn
        == RAMP_PRODUCTION_FACILITY_URN
    )

    assert details.country_code == RAMP_COUNTRY
    assert details.ad_type == RAMP_AD_TYPE
    assert details.ad_status == RAMP_AD_STATUS
    assert details.physical_form == RAMP_PHYSICAL_FORM

    print("\nRAMP configuration:")
    print("Owner:", details.owner_urn)
    print(
        "Production facility:",
        details.production_facility_urn,
    )
    print("Country:", details.country_code)
    print("Advertisement type:", details.ad_type)
    print("Physical form:", details.physical_form)

    # ----------------------------------------------------------
    # 5. Initialize mapper
    # ----------------------------------------------------------

    mapper = CirculoosRampMapper(
        entity_manager=entity_manager,
        registry=registry,
    )

    # ----------------------------------------------------------
    # 6. Generate RAMP payload
    # ----------------------------------------------------------

    payload = mapper.build(
        timber_id=TIMBER_ID,
        advertisement_urn=advertisement_urn,
        details=details,
    )

    assert isinstance(payload, list)
    assert len(payload) == 1

    ramp_ad = payload[0]

    # Verify advertisement identity.
    assert ramp_ad["id"] == advertisement_urn
    assert ramp_ad["type"] == "others"

    # Verify Wood relationship.
    assert ramp_ad["refMaterial"] == {
        "type": "Relationship",
        "object": wood_urn,
    }

    # Verify material quantity representation.
    assert (
        ramp_ad["materialQuantity"]["type"]
        == "Property"
    )

    assert (
        ramp_ad["materialQuantity"]["unitCode"]
        == "MTK"
    )

    assert (
        ramp_ad["physicalFormCategory"]["value"]
        == "bySurface"
    )

    # Verify owner and production facility.
    assert (
        ramp_ad["ownedBy"]["object"]
        == RAMP_OWNER_URN
    )

    assert (
        ramp_ad["productionFacility"]["object"]
        == RAMP_PRODUCTION_FACILITY_URN
    )

    # Verify all required advertisement fields.
    required_fields = (
        "id",
        "type",
        "materialAdTitle",
        "materialTypeL0",
        "materialTypeL1",
        "physicalFormCategory",
        "imageURL",
        "materialPrice",
        "availableFrom",
        "materialAdType",
        "materialDescription",
        "materialAdStatus",
        "materialQuantity",
        "ownedBy",
        "productionFacility",
        "materialToSellOrBuy",
        "CountryCode",
    )

    for field in required_fields:
        assert field in ramp_ad, (
            f"Missing RAMP field: {field}"
        )

    print("\nGenerated RAMP advertisement:")
    print(
        json.dumps(
            payload,
            indent=2,
        )
    )

    # ----------------------------------------------------------
    # 7. Save array-based JSON payload
    # ----------------------------------------------------------

    output_path = mapper.save(
        timber_id=TIMBER_ID,
        advertisement_urn=advertisement_urn,
        details=details,
    )

    saved_payload = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert saved_payload == payload

    assert output_path.name == (
        "circuloos_ramp_ad_AD-001.json"
    )

    # ----------------------------------------------------------
    # 8. Verify registry remains unchanged
    # ----------------------------------------------------------

    registry_after = registry.load(
        TIMBER_ID
    )

    assert registry_after == registry_data, (
        "RAMP mapping unexpectedly modified the registry."
    )

    assert (
        registry_after["wood"]["status"]
        == "local_only"
    )

    assert (
        registry_after["advertisements"][0]["status"]
        == "local_only"
    )

    print("\nSaved RAMP payload:", output_path)
    print("Advertisement URN persistence: PASS")
    print("refMaterial relationship: PASS")
    print("RAMP configuration defaults: PASS")
    print("JSON array format: PASS")
    print("Registry unchanged: PASS")
    print("\nRAMP mapping test: PASS")


if __name__ == "__main__":
    main()
