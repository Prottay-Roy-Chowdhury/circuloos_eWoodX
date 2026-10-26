"""CIRCULOOS publication service for eWoodX.

Uses existing local mappings and the existing OrionClient.

Offline operations:
- preview_wood()
- preview_advertisement()

Live operations (explicitly disabled by default):
- publish_wood()
- publish_advertisement()

No local timber IDs or advertisement URNs are allocated here.
No generic workspace modules are modified.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any

from framework.workspace import EntityManager

from .entity_registry import (
    CirculoosEntityRegistry,
    STATUS_PUBLISHED,
)
from .wood_mapper import (
    WOOD_PAYLOAD_FILE,
    WOOD_CONTEXT_URL,
)
from .ramp_mapper import CirculoosRampMapper
from .orion import OrionClient
from .client import CirculoosHTTPError


RAMP_CONTEXT_URL = (
    "http://circuloos-ld-context/"
    "circuloos-context.jsonld"
)

DEFAULT_TENANT = "circuloos_ewoodx_material"


class CirculoosPublicationService:
    """Validate and optionally publish mapped timber entities."""

    def __init__(
        self,
        entity_manager: EntityManager,
        orion: OrionClient | None = None,
        registry: CirculoosEntityRegistry | None = None,
        tenant: str = DEFAULT_TENANT,
        allow_live: bool = False,
    ) -> None:

        if not isinstance(entity_manager, EntityManager):
            raise TypeError(
                "entity_manager must be an EntityManager."
            )

        if orion is not None and not isinstance(
            orion, OrionClient
        ):
            raise TypeError(
                "orion must be an OrionClient."
            )

        if not isinstance(tenant, str) or not tenant.strip():
            raise ValueError(
                "tenant must be a non-empty string."
            )

        if not isinstance(allow_live, bool):
            raise TypeError(
                "allow_live must be a boolean."
            )

        self.entity_manager = entity_manager
        self.orion = orion
        self.tenant = tenant.strip()
        self.allow_live = allow_live

        self.registry = (
            registry
            if registry is not None
            else CirculoosEntityRegistry(entity_manager)
        )

        if not isinstance(
            self.registry, CirculoosEntityRegistry
        ):
            raise TypeError(
                "registry must be a CirculoosEntityRegistry."
            )

        if self.registry.entity_manager is not entity_manager:
            raise ValueError(
                "Registry and service must use "
                "the same EntityManager."
            )

        self.ramp_mapper = CirculoosRampMapper(
            entity_manager=entity_manager,
            registry=self.registry,
        )

    def _require_live(self) -> OrionClient:
        """Reject all remote operations unless explicitly enabled."""

        if not self.allow_live:
            raise PermissionError(
                "Live CIRCULOOS operations are disabled. "
                "Initialize with allow_live=True only "
                "when publication is explicitly intended."
            )

        if self.orion is None:
            raise RuntimeError(
                "An OrionClient is required for live operations."
            )

        return self.orion

    def _registry_data(
        self,
        timber_id: str,
    ) -> dict[str, Any]:

        data = self.registry.load(timber_id)

        if data is None:
            raise FileNotFoundError(
                "CIRCULOOS registry not found. "
                "Prepare the mapping first."
            )

        return data

    @staticmethod
    def _read_payload(
        path: Path,
    ) -> dict[str, Any]:
        """Read one NGSI-LD entity stored in a JSON array."""

        if not path.is_file():
            raise FileNotFoundError(
                f"CIRCULOOS payload missing: {path}"
            )

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if (
            not isinstance(data, list)
            or len(data) != 1
            or not isinstance(data[0], dict)
        ):
            raise ValueError(
                "Payload must be a JSON array "
                "containing exactly one entity."
            )

        return data[0]

    @staticmethod
    def _validate_identity(
        entity: dict[str, Any],
        expected_urn: str,
        expected_type: str,
    ) -> None:

        if entity.get("id") != expected_urn:
            raise ValueError(
                "Payload URN does not match registry."
            )

        if entity.get("type") != expected_type:
            raise ValueError(
                "Payload type does not match registry."
            )

    @staticmethod
    def _quantity(
        entity: dict[str, Any],
        attribute: str,
    ) -> float:

        prop = entity.get(attribute)

        if (
            not isinstance(prop, dict)
            or prop.get("type") != "Property"
            or prop.get("unitCode") != "MTK"
        ):
            raise ValueError(
                f"{attribute} must be an MTK Property."
            )

        value = prop.get("value")

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(
                f"{attribute} must contain a "
                "finite positive number."
            )

        return float(value)

    @staticmethod
    def _property_value(
        entity: dict[str, Any],
        attribute: str,
    ) -> Any:

        prop = entity.get(attribute)

        if (
            not isinstance(prop, dict)
            or prop.get("type") != "Property"
            or "value" not in prop
        ):
            raise ValueError(
                f"Invalid or missing Property: {attribute}"
            )

        return prop["value"]

    @staticmethod
    def _relationship_object(
        entity: dict[str, Any],
        attribute: str,
    ) -> str:

        rel = entity.get(attribute)

        if (
            not isinstance(rel, dict)
            or rel.get("type") != "Relationship"
            or not isinstance(rel.get("object"), str)
            or not rel["object"]
        ):
            raise ValueError(
                f"Invalid or missing Relationship: {attribute}"
            )

        return rel["object"]

    def _advertisement_record(
        self,
        registry_data: dict[str, Any],
        sequence: int,
    ) -> dict[str, Any]:

        sequence = (
            self.registry.urn_generator
            .validate_ad_sequence(sequence)
        )

        advertisement = next(
            (
                ad
                for ad in registry_data["advertisements"]
                if ad["sequence"] == sequence
            ),
            None,
        )

        if advertisement is None:
            raise ValueError(
                f"Advertisement AD-{sequence:03d} "
                "not found in registry."
            )

        return advertisement

    # ----------------------------------------------------------
    # Offline previews
    # ----------------------------------------------------------

    def preview_wood(
        self,
        timber_id: str,
    ) -> dict[str, Any]:
        """Validate and return the existing Wood payload."""

        registry_data = self._registry_data(timber_id)

        root = self.registry._resolve_timber(timber_id)
        path = root / WOOD_PAYLOAD_FILE

        entity = self._read_payload(path)

        wood_urn = registry_data["wood"]["urn"]

        self._validate_identity(
            entity, wood_urn, "wood"
        )

        self._quantity(entity, "quantity")

        return {
            "timber_id": timber_id,
            "urn": wood_urn,
            "entity_type": "wood",
            "status": registry_data["wood"]["status"],
            "tenant": self.tenant,
            "context": WOOD_CONTEXT_URL,
            "payload_path": path,
            "payload": [deepcopy(entity)],
        }

    def preview_advertisement(
        self,
        timber_id: str,
        sequence: int,
    ) -> dict[str, Any]:
        """Validate an existing RAMP advertisement locally."""

        registry_data = self._registry_data(timber_id)

        advertisement = self._advertisement_record(
            registry_data, sequence
        )

        wood_preview = self.preview_wood(timber_id)

        root = self.registry._resolve_timber(timber_id)

        path = (
            root
            / f"circuloos_ramp_ad_AD-{sequence:03d}.json"
        )

        entity = self._read_payload(path)

        self._validate_identity(
            entity, advertisement["urn"], "others"
        )

        expected_wood_urn = wood_preview["urn"]

        if (
            self._relationship_object(entity, "refMaterial")
            != expected_wood_urn
        ):
            raise ValueError(
                "Advertisement refMaterial does not "
                "match the registered Wood URN."
            )

        if advertisement["ref_material"] != expected_wood_urn:
            raise ValueError(
                "Registry refMaterial mismatch."
            )

        wood_quantity = self._quantity(
            wood_preview["payload"][0], "quantity"
        )

        ad_quantity = self._quantity(
            entity, "materialQuantity"
        )

        if not math.isclose(
            wood_quantity,
            ad_quantity,
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "Advertisement quantity does not match Wood."
            )

        required_properties = (
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
            "materialToSellOrBuy",
            "CountryCode",
        )

        for attribute in required_properties:
            self._property_value(entity, attribute)

        for attribute in (
            "ownedBy",
            "productionFacility",
        ):
            self._relationship_object(entity, attribute)

        if (
            self._property_value(
                entity, "physicalFormCategory"
            ) != "bySurface"
        ):
            raise ValueError(
                "Only bySurface advertisements are supported."
            )

        return {
            "timber_id": timber_id,
            "urn": advertisement["urn"],
            "wood_urn": expected_wood_urn,
            "sequence": sequence,
            "entity_type": "others",
            "status": advertisement["status"],
            "tenant": self.tenant,
            "context": RAMP_CONTEXT_URL,
            "payload_path": path,
            "payload": [deepcopy(entity)],
        }

    # ----------------------------------------------------------
    # Remote helpers
    # ----------------------------------------------------------

    def _remote_entity(
        self,
        entity_id: str,
        context: str,
    ) -> dict[str, Any] | None:
        """Retrieve remote entity, returning None only on 404."""

        orion = self._require_live()

        try:
            return orion.get_entity(
                entity_id,
                tenant=self.tenant,
                context=context,
            )
        except CirculoosHTTPError as exc:
            if exc.status_code == 404:
                return None
            raise

    def _publish(
        self,
        preview: dict[str, Any],
        *,
        overwrite: bool,
    ) -> dict[str, Any]:
        """Upsert and verify one prepared entity."""

        orion = self._require_live()

        urn = preview["urn"]
        context = preview["context"]

        existing = self._remote_entity(
            urn, context
        )

        if existing is not None and not overwrite:
            raise FileExistsError(
                f"Remote entity already exists: {urn}. "
                "Set overwrite=True only when an "
                "update is explicitly intended."
            )

        orion.upsert_entities(
            preview["payload"],
            tenant=self.tenant,
            context=context,
        )

        readback = self._remote_entity(
            urn, context
        )

        if readback is None:
            raise RuntimeError(
                "Orion upsert returned successfully, "
                "but entity readback returned 404."
            )

        self._validate_identity(
            readback,
            urn,
            preview["entity_type"],
        )

        if preview["entity_type"] == "wood":
            expected_quantity = self._quantity(
                preview["payload"][0], "quantity"
            )
            actual_quantity = self._quantity(
                readback, "quantity"
            )

        else:
            expected_quantity = self._quantity(
                preview["payload"][0],
                "materialQuantity",
            )
            actual_quantity = self._quantity(
                readback,
                "materialQuantity",
            )

            expected_ref = preview["wood_urn"]

            if (
                self._relationship_object(
                    readback, "refMaterial"
                ) != expected_ref
            ):
                raise RuntimeError(
                    "Remote advertisement refMaterial "
                    "verification failed."
                )

        if not math.isclose(
            expected_quantity,
            actual_quantity,
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise RuntimeError(
                "Remote quantity verification failed."
            )

        return {
            "urn": urn,
            "tenant": self.tenant,
            "verified": True,
            "created": existing is None,
            "readback": readback,
        }

    # ----------------------------------------------------------
    # Live publication
    # ----------------------------------------------------------

    def publish_wood(
        self,
        timber_id: str,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Publish and verify Wood before updating registry."""

        self._require_live()

        preview = self.preview_wood(timber_id)

        result = self._publish(
            preview,
            overwrite=overwrite,
        )

        self.registry.set_publication_status(
            timber_id,
            STATUS_PUBLISHED,
        )

        return result

    def publish_advertisement(
        self,
        timber_id: str,
        sequence: int,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Publish and verify a RAMP advertisement.

        The referenced Wood must already exist remotely.
        """

        self._require_live()

        preview = self.preview_advertisement(
            timber_id, sequence
        )

        wood = self._remote_entity(
            preview["wood_urn"],
            WOOD_CONTEXT_URL,
        )

        if wood is None:
            raise FileNotFoundError(
                "Referenced Wood entity is not present "
                "in Orion. Publish Wood first."
            )

        self._validate_identity(
            wood,
            preview["wood_urn"],
            "wood",
        )

        result = self._publish(
            preview,
            overwrite=overwrite,
        )

        self.registry.set_publication_status(
            timber_id,
            STATUS_PUBLISHED,
            advertisement_urn=preview["urn"],
        )

        return result