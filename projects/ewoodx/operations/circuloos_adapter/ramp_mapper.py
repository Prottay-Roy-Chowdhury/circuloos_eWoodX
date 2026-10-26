"""Map eWoodX timber entities to CIRCULOOS RAMP advertisements.

The mapper:
- Uses an existing advertisement allocated by the registry.
- Reads the saved Wood payload for material quantity.
- Requires explicit marketplace metadata.
- Generates an NGSI-LD batch-compatible JSON array.
- Saves the advertisement in the timber directory.

It does not allocate advertisements or publish to Orion-LD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from framework.workspace import EntityManager

from .entity_registry import CirculoosEntityRegistry
from .wood_mapper import WOOD_PAYLOAD_FILE
from .config import (
    RAMP_OWNER_URN,
    RAMP_PRODUCTION_FACILITY_URN,
    RAMP_COUNTRY,
    RAMP_AD_TYPE,
    RAMP_AD_STATUS,
    RAMP_PHYSICAL_FORM,
)


@dataclass(frozen=True)
class RampAdDetails:
    """Advertisement-specific information with RAMP defaults."""

    title: str
    description: str

    material_type_l0: str
    material_type_l1: str
    material_to_sell_or_buy: str

    available_from: str
    price: float
    image_url: str = ""

    owner_urn: str = RAMP_OWNER_URN
    production_facility_urn: str = RAMP_PRODUCTION_FACILITY_URN

    country_code: str = RAMP_COUNTRY
    ad_type: str = RAMP_AD_TYPE
    ad_status: str = RAMP_AD_STATUS
    physical_form: str = RAMP_PHYSICAL_FORM


def _property(
    value: Any,
    unit_code: str | None = None,
) -> dict[str, Any]:

    result = {
        "type": "Property",
        "value": value,
    }

    if unit_code is not None:
        result["unitCode"] = unit_code

    return result


def _relationship(
    urn: str,
) -> dict[str, str]:

    return {
        "type": "Relationship",
        "object": urn,
    }


def _required_string(
    value: str,
    field: str,
) -> str:

    if not isinstance(value, str):
        raise TypeError(
            f"{field} must be a string."
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"{field} cannot be empty."
        )

    return value


def _save_json_atomic(
    path: Path,
    payload: list[dict[str, Any]],
) -> None:

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:

            temporary_path = Path(file.name)

            json.dump(
                payload,
                file,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )

            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temporary_path,
            path,
        )

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()


class CirculoosRampMapper:
    """Generate RAMP advertisements for existing timber entities."""

    def __init__(
        self,
        entity_manager: EntityManager,
        registry: CirculoosEntityRegistry | None = None,
    ) -> None:

        if not isinstance(
            entity_manager,
            EntityManager,
        ):
            raise TypeError(
                "entity_manager must be an EntityManager."
            )

        self.entity_manager = entity_manager

        self.registry = (
            registry
            if registry is not None
            else CirculoosEntityRegistry(
                entity_manager=entity_manager
            )
        )

        if not isinstance(
            self.registry,
            CirculoosEntityRegistry,
        ):
            raise TypeError(
                "Invalid CIRCULOOS registry."
            )

        if self.registry.entity_manager is not entity_manager:
            raise ValueError(
                "Registry and mapper must use "
                "the same EntityManager."
            )

    def _load_wood(
        self,
        timber_id: str,
        expected_urn: str,
    ) -> dict[str, Any]:
        """Read the previously generated Wood payload."""

        entity = self.entity_manager.load_entity(
            timber_id
        )

        path = entity.root / WOOD_PAYLOAD_FILE

        if not path.is_file():
            raise FileNotFoundError(
                f"Wood payload not found: {path}. "
                "Run the Wood mapper first."
            )

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(file)

        if (
            not isinstance(payload, list)
            or len(payload) != 1
            or not isinstance(payload[0], dict)
        ):
            raise ValueError(
                "Wood payload must contain exactly "
                "one entity in a JSON array."
            )

        wood = payload[0]

        if (
            wood.get("id") != expected_urn
            or wood.get("type") != "wood"
        ):
            raise ValueError(
                "Wood payload does not match "
                "the registry."
            )

        return wood

    @staticmethod
    def _validate_details(
        details: RampAdDetails,
    ) -> None:

        if not isinstance(details, RampAdDetails):
            raise TypeError(
                "details must be RampAdDetails."
            )

        for field in (
            "title",
            "description",
            "material_type_l0",
            "material_type_l1",
            "material_to_sell_or_buy",
            "owner_urn",
            "production_facility_urn",
            "country_code",
            "available_from",
        ):
            _required_string(
                getattr(details, field),
                field,
            )

        for field in (
            "owner_urn",
            "production_facility_urn",
        ):
            urn = getattr(details, field).strip()

            if not urn.startswith("urn:ngsi-ld:"):
                raise ValueError(
                    f"{field} must be an NGSI-LD URN."
                )

        try:
            date.fromisoformat(
                details.available_from
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "available_from must use YYYY-MM-DD."
            ) from exc

        if details.ad_type not in {"Sell", "Buy"}:
            raise ValueError(
                "ad_type must be Sell or Buy."
            )

        if details.physical_form != "bySurface":
            raise ValueError(
                "This mapper currently supports "
                "bySurface advertisements only."
            )

        if (
            isinstance(details.price, bool)
            or not isinstance(
                details.price,
                (int, float),
            )
            or not math.isfinite(details.price)
            or details.price < 0
        ):
            raise ValueError(
                "price must be a finite "
                "non-negative number."
            )

        if not isinstance(details.image_url, str):
            raise TypeError(
                "image_url must be a string."
            )

        if not isinstance(details.ad_status, str):
            raise TypeError(
                "ad_status must be a string."
            )

        _required_string(
            details.ad_status,
            "ad_status",
        )

    def build(
        self,
        timber_id: str,
        advertisement_urn: str,
        details: RampAdDetails,
    ) -> list[dict[str, Any]]:
        """Generate one RAMP advertisement in a JSON array."""

        self._validate_details(
            details
        )

        registry_data = self.registry.load(
            timber_id
        )

        if registry_data is None:
            raise FileNotFoundError(
                "CIRCULOOS registry not found."
            )

        advertisement = next(
            (
                ad
                for ad in registry_data["advertisements"]
                if ad["urn"] == advertisement_urn
            ),
            None,
        )

        if advertisement is None:
            raise ValueError(
                "Advertisement URN is not registered "
                "for this timber."
            )

        wood_urn = registry_data["wood"]["urn"]

        if advertisement["ref_material"] != wood_urn:
            raise ValueError(
                "Advertisement refMaterial mismatch."
            )

        wood = self._load_wood(
            timber_id,
            wood_urn,
        )

        quantity_property = wood.get(
            "quantity"
        )

        if (
            not isinstance(quantity_property, dict)
            or quantity_property.get("type") != "Property"
            or quantity_property.get("unitCode") != "MTK"
        ):
            raise ValueError(
                "Wood quantity must be an MTK Property."
            )

        quantity = quantity_property.get("value")

        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or not math.isfinite(quantity)
            or quantity <= 0
        ):
            raise ValueError(
                "Invalid Wood surface quantity."
            )

        payload = {
            "id": advertisement_urn,
            "type": "others",

            "materialAdTitle": _property(
                details.title.strip()
            ),

            "materialTypeL0": _property(
                details.material_type_l0.strip()
            ),

            "materialTypeL1": _property(
                details.material_type_l1.strip()
            ),

            "physicalFormCategory": _property(
                details.physical_form
            ),

            "imageURL": _property(
                details.image_url.strip()
            ),

            "materialPrice": _property(
                float(details.price)
            ),

            "availableFrom": _property(
                details.available_from
            ),

            "materialAdType": _property(
                details.ad_type
            ),

            "materialDescription": _property(
                details.description.strip()
            ),

            "materialAdStatus": _property(
                details.ad_status.strip()
            ),

            "materialQuantity": _property(
                quantity,
                "MTK",
            ),

            "ownedBy": _relationship(
                details.owner_urn.strip()
            ),

            "productionFacility": _relationship(
                details.production_facility_urn.strip()
            ),

            "materialToSellOrBuy": _property(
                details.material_to_sell_or_buy.strip()
            ),

            "CountryCode": _property(
                details.country_code.strip()
            ),

            "refMaterial": _relationship(
                wood_urn
            ),
        }

        return [payload]

    def save(
        self,
        timber_id: str,
        advertisement_urn: str,
        details: RampAdDetails,
    ) -> Path:
        """Save an array-based RAMP advertisement JSON."""

        payload = self.build(
            timber_id,
            advertisement_urn,
            details,
        )

        registry_data = self.registry.load(
            timber_id
        )

        advertisement = next(
            ad
            for ad in registry_data["advertisements"]
            if ad["urn"] == advertisement_urn
        )

        sequence = advertisement["sequence"]

        entity = self.entity_manager.load_entity(
            timber_id
        )

        output_path = (
            entity.root
            / f"circuloos_ramp_ad_AD-{sequence:03d}.json"
        )

        _save_json_atomic(
            output_path,
            payload,
        )

        return output_path