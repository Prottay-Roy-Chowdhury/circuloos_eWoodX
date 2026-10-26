"""Local CIRCULOOS mapping orchestration for eWoodX timber.

Responsibilities:
- Prepare or regenerate Wood payloads.
- Explicitly create new RAMP advertisements.
- Update existing RAMP advertisement payloads.
- Inspect persistent mappings and local payload paths.

This service does not:
- Publish entities to CIRCULOOS.
- Modify publication statuses.
- Allocate local eWoodX timber IDs.
- Modify the generic workspace framework.

The registry and mappers remain responsible for their
respective identity and payload operations.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from framework.workspace import EntityManager

from .entity_registry import CirculoosEntityRegistry
from .wood_mapper import (
    CirculoosWoodMapper,
    WOOD_PAYLOAD_FILE,
)
from .ramp_mapper import (
    CirculoosRampMapper,
    RampAdDetails,
)


class CirculoosMappingService:
    """Coordinate local CIRCULOOS mappings for timber entities."""

    def __init__(
        self,
        entity_manager: EntityManager,
        registry: CirculoosEntityRegistry | None = None,
        include_thickness: bool = False,
        include_context: bool = False,
    ) -> None:

        if not isinstance(entity_manager, EntityManager):
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
                "registry must be a CirculoosEntityRegistry."
            )

        if self.registry.entity_manager is not entity_manager:
            raise ValueError(
                "Registry and service must use "
                "the same EntityManager instance."
            )

        self.wood_mapper = CirculoosWoodMapper(
            entity_manager=entity_manager,
            registry=self.registry,
            include_thickness=include_thickness,
            include_context=include_context,
        )

        self.ramp_mapper = CirculoosRampMapper(
            entity_manager=entity_manager,
            registry=self.registry,
        )

    def _timber_root(
        self,
        timber_id: str,
    ) -> Path:
        """Resolve and validate an existing timber entity."""

        return self.registry._resolve_timber(
            timber_id
        )

    def _validate_wood_for_advertisement(
        self,
        timber_id: str,
        wood_urn: str,
    ) -> None:
        """Ensure the saved Wood payload is usable by RAMP.

        This validation is performed before allocating a
        new advertisement, preventing avoidable allocations
        when the Wood payload is missing or invalid.
        """

        wood = self.ramp_mapper._load_wood(
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
                "Wood payload must contain a quantity "
                "Property with unitCode M TK."
                .replace("M TK", "MTK")
            )

        quantity = quantity_property.get("value")

        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or not math.isfinite(quantity)
            or quantity <= 0
        ):
            raise ValueError(
                "Wood surface quantity must be "
                "a finite positive number."
            )

    def _require_registry(
        self,
        timber_id: str,
    ) -> dict[str, Any]:
        """Load an existing registry without creating one."""

        registry_data = self.registry.load(
            timber_id
        )

        if registry_data is None:
            raise FileNotFoundError(
                "CIRCULOOS registry not found. "
                "Run prepare_wood() first."
            )

        return registry_data

    def _prepare_advertisement_prerequisites(
        self,
        timber_id: str,
        details: RampAdDetails,
    ) -> dict[str, Any]:
        """Validate details and existing Wood mapping."""

        # Reject invalid advertisement details before any
        # identity allocation or payload write.
        self.ramp_mapper._validate_details(
            details
        )

        registry_data = self._require_registry(
            timber_id
        )

        self._validate_wood_for_advertisement(
            timber_id,
            registry_data["wood"]["urn"],
        )

        return registry_data

    @staticmethod
    def _advertisement_result(
        timber_id: str,
        wood_urn: str,
        advertisement: dict[str, Any],
        output_path: Path,
        is_new: bool,
    ) -> dict[str, Any]:
        """Return consistent advertisement operation metadata."""

        return {
            "timber_id": timber_id,
            "wood_urn": wood_urn,
            "advertisement_urn": advertisement["urn"],
            "sequence": advertisement["sequence"],
            "advertisement_status": advertisement["status"],
            "is_new": is_new,
            "payload_path": output_path,
        }

    # ----------------------------------------------------------
    # Wood mapping
    # ----------------------------------------------------------

    def prepare_wood(
        self,
        timber_id: str,
    ) -> dict[str, Any]:
        """Create or regenerate the local Wood payload.

        The existing Wood URN is reused.
        No advertisement identity is allocated.
        No publication status is changed.
        """

        output_path = self.wood_mapper.save(
            timber_id
        )

        registry_data = self._require_registry(
            timber_id
        )

        return {
            "timber_id": timber_id,
            "wood_urn": registry_data["wood"]["urn"],
            "wood_status": registry_data["wood"]["status"],
            "payload_path": output_path,
        }

    # ----------------------------------------------------------
    # Advertisement creation
    # ----------------------------------------------------------

    def create_advertisement(
        self,
        timber_id: str,
        details: RampAdDetails,
    ) -> dict[str, Any]:
        """Allocate and generate a NEW RAMP advertisement.

        Every successful invocation allocates a new sequence.

        The Wood payload must already exist.

        If payload generation fails after allocation, the
        allocated URN remains in the registry. The service
        does not silently reuse or roll back identities.
        """

        registry_data = (
            self._prepare_advertisement_prerequisites(
                timber_id,
                details,
            )
        )

        advertisement = (
            self.registry.allocate_advertisement(
                timber_id
            )
        )

        output_path = self.ramp_mapper.save(
            timber_id=timber_id,
            advertisement_urn=advertisement["urn"],
            details=details,
        )

        return self._advertisement_result(
            timber_id=timber_id,
            wood_urn=registry_data["wood"]["urn"],
            advertisement=advertisement,
            output_path=output_path,
            is_new=True,
        )

    # ----------------------------------------------------------
    # Advertisement update
    # ----------------------------------------------------------

    def update_advertisement(
        self,
        timber_id: str,
        sequence: int,
        details: RampAdDetails,
    ) -> dict[str, Any]:
        """Regenerate an EXISTING advertisement payload.

        No new advertisement identity is allocated.
        The registered URN and sequence remain unchanged.

        This is a local JSON update only. If the entity
        was previously published, Orion is not updated.
        """

        registry_data = (
            self._prepare_advertisement_prerequisites(
                timber_id,
                details,
            )
        )

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
                "is not registered for this timber."
            )

        output_path = self.ramp_mapper.save(
            timber_id=timber_id,
            advertisement_urn=advertisement["urn"],
            details=details,
        )

        return self._advertisement_result(
            timber_id=timber_id,
            wood_urn=registry_data["wood"]["urn"],
            advertisement=advertisement,
            output_path=output_path,
            is_new=False,
        )

    # ----------------------------------------------------------
    # Mapping inspection
    # ----------------------------------------------------------

    def get_mapping(
        self,
        timber_id: str,
    ) -> dict[str, Any] | None:
        """Inspect existing mapping information.

        This method does not create or modify any files.
        Returns None when no CIRCULOOS registry exists.
        """

        registry_data = self.registry.load(
            timber_id
        )

        if registry_data is None:
            return None

        timber_root = self._timber_root(
            timber_id
        )

        wood_path = (
            timber_root / WOOD_PAYLOAD_FILE
        )

        advertisements = []

        for advertisement in registry_data["advertisements"]:

            sequence = advertisement["sequence"]

            payload_path = (
                timber_root
                / f"circuloos_ramp_ad_AD-{sequence:03d}.json"
            )

            advertisements.append({
                "sequence": sequence,
                "urn": advertisement["urn"],
                "status": advertisement["status"],
                "ref_material": advertisement["ref_material"],
                "payload_path": (
                    payload_path
                    if payload_path.is_file()
                    else None
                ),
            })

        return {
            "timber_id": timber_id,
            "registry_path": self.registry.registry_path(
                timber_id
            ),
            "wood": {
                "urn": registry_data["wood"]["urn"],
                "status": registry_data["wood"]["status"],
                "payload_path": (
                    wood_path
                    if wood_path.is_file()
                    else None
                ),
            },
            "advertisements": advertisements,
        }