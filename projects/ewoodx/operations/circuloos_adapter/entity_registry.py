"""Persistent CIRCULOOS identity registry for eWoodX timber entities.

The registry is stored inside each existing timber directory.

Responsibilities:
- Resolve existing timber entities through EntityManager.
- Allocate and persist Wood URNs.
- Allocate and persist RAMP advertisement URNs.
- Retrieve existing mappings.
- Record publication status after external verification.

No CIRCULOOS network requests are performed here.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from framework.workspace import EntityManager

from projects.ewoodx.config.entity import (
    TIMBER_ENTITY_TYPE,
)

from .urn_generator import CirculoosURNGenerator


REGISTRY_FILE = "circuloos_registry.json"
REGISTRY_VERSION = 1

STATUS_LOCAL_ONLY = "local_only"
STATUS_PUBLISHED = "published"
STATUS_FAILED = "failed"

PUBLICATION_STATUSES = {
    STATUS_LOCAL_ONLY,
    STATUS_PUBLISHED,
    STATUS_FAILED,
}


def _utc_now() -> str:
    """Return the current UTC timestamp."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _write_json_atomic(
    path: Path,
    data: dict[str, Any],
) -> None:
    """Atomically replace a JSON file in the same directory."""

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
                data,
                file,
                indent=2,
                ensure_ascii=False,
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


class CirculoosEntityRegistry:
    """Manage persistent CIRCULOOS mappings for timber."""

    def __init__(
        self,
        entity_manager: EntityManager,
        urn_generator: CirculoosURNGenerator | None = None,
    ) -> None:

        if not isinstance(
            entity_manager,
            EntityManager,
        ):
            raise TypeError(
                "entity_manager must be an EntityManager."
            )

        self.entity_manager = entity_manager

        self.urn_generator = (
            urn_generator
            if urn_generator is not None
            else CirculoosURNGenerator()
        )

        if not isinstance(
            self.urn_generator,
            CirculoosURNGenerator,
        ):
            raise TypeError(
                "urn_generator must be a "
                "CirculoosURNGenerator."
            )

    def _resolve_timber(
        self,
        timber_id: str,
    ) -> Path:
        """Resolve and validate an existing timber entity."""

        timber_id = (
            self.urn_generator
            .validate_timber_id(timber_id)
        )

        entity = self.entity_manager.load_entity(
            timber_id
        )

        with entity.manifest.open(
            "r",
            encoding="utf-8",
        ) as file:
            manifest = json.load(file)

        if manifest.get("entity_id") != timber_id:
            raise ValueError(
                "Entity manifest ID does not match "
                f"the requested timber: {timber_id}"
            )

        if manifest.get("entity_type") != TIMBER_ENTITY_TYPE:
            raise ValueError(
                f"Entity is not a timber: {timber_id}"
            )

        return entity.root

    def registry_path(
        self,
        timber_id: str,
    ) -> Path:
        """Return the registry path for an existing timber."""

        return (
            self._resolve_timber(timber_id)
            / REGISTRY_FILE
        )

    def _new_registry(
        self,
        timber_id: str,
    ) -> dict[str, Any]:
        """Build the initial registry structure."""

        now = _utc_now()

        return {
            "schema_version": REGISTRY_VERSION,
            "timber_id": timber_id,
            "namespace": self.urn_generator.namespace,
            "created_at": now,
            "updated_at": now,
            "wood": {
                "urn": self.urn_generator.wood_urn(
                    timber_id
                ),
                "type": "wood",
                "status": STATUS_LOCAL_ONLY,
                "published_at": None,
            },
            "advertisements": [],
        }

    def _validate_registry(
        self,
        data: dict[str, Any],
        timber_id: str,
    ) -> None:
        """Reject inconsistent or unsupported registry data."""

        if not isinstance(data, dict):
            raise ValueError(
                "CIRCULOOS registry must be a JSON object."
            )

        if data.get("schema_version") != REGISTRY_VERSION:
            raise ValueError(
                "Unsupported CIRCULOOS registry version."
            )

        if data.get("timber_id") != timber_id:
            raise ValueError(
                "CIRCULOOS registry timber ID mismatch."
            )

        if data.get("namespace") != self.urn_generator.namespace:
            raise ValueError(
                "CIRCULOOS registry namespace mismatch."
            )

        wood = data.get("wood")

        if not isinstance(wood, dict):
            raise ValueError(
                "Missing Wood registry information."
            )

        expected_wood_urn = (
            self.urn_generator.wood_urn(timber_id)
        )

        if wood.get("urn") != expected_wood_urn:
            raise ValueError(
                "Stored Wood URN does not match "
                "the configured naming convention."
            )

        if wood.get("type") != "wood":
            raise ValueError(
                "Invalid Wood entity type."
            )

        if wood.get("status") not in PUBLICATION_STATUSES:
            raise ValueError(
                "Invalid Wood publication status."
            )

        ads = data.get("advertisements")

        if not isinstance(ads, list):
            raise ValueError(
                "Advertisements must be a list."
            )

        seen_sequences = set()
        seen_urns = set()

        for ad in ads:
            if not isinstance(ad, dict):
                raise ValueError(
                    "Invalid advertisement record."
                )

            sequence = (
                self.urn_generator
                .validate_ad_sequence(
                    ad.get("sequence")
                )
            )

            expected_urn = (
                self.urn_generator.advertisement_urn(
                    timber_id,
                    sequence,
                )
            )

            if ad.get("urn") != expected_urn:
                raise ValueError(
                    "Advertisement URN mismatch."
                )

            if ad.get("ref_material") != expected_wood_urn:
                raise ValueError(
                    "Advertisement refMaterial mismatch."
                )

            if ad.get("type") != "others":
                raise ValueError(
                    "Invalid advertisement entity type."
                )

            if ad.get("status") not in PUBLICATION_STATUSES:
                raise ValueError(
                    "Invalid advertisement publication status."
                )

            if (
                sequence in seen_sequences
                or expected_urn in seen_urns
            ):
                raise ValueError(
                    "Duplicate advertisement in registry."
                )

            seen_sequences.add(sequence)
            seen_urns.add(expected_urn)

    def load(
        self,
        timber_id: str,
    ) -> dict[str, Any] | None:
        """Read an existing registry without creating one."""

        timber_id = (
            self.urn_generator
            .validate_timber_id(timber_id)
        )

        path = self.registry_path(
            timber_id
        )

        if not path.exists():
            return None

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        self._validate_registry(
            data,
            timber_id,
        )

        return deepcopy(data)

    def ensure(
        self,
        timber_id: str,
    ) -> dict[str, Any]:
        """Create a registry if absent, otherwise reuse it."""

        timber_id = (
            self.urn_generator
            .validate_timber_id(timber_id)
        )

        existing = self.load(
            timber_id
        )

        if existing is not None:
            return existing

        data = self._new_registry(
            timber_id
        )

        path = self.registry_path(
            timber_id
        )

        # Exclusive creation avoids silently overwriting
        # a registry that appeared after the initial check.
        with path.open(
            "x",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.write("\n")

        return deepcopy(data)

    def allocate_advertisement(
        self,
        timber_id: str,
    ) -> dict[str, Any]:
        """Allocate and persist the next advertisement identity.

        Each explicit call allocates a new advertisement.
        This operation is not idempotent.
        """

        registry = self.ensure(
            timber_id
        )

        existing_sequences = [
            ad["sequence"]
            for ad in registry["advertisements"]
        ]

        sequence = (
            max(existing_sequences, default=0) + 1
        )

        self.urn_generator.validate_ad_sequence(
            sequence
        )

        now = _utc_now()

        advertisement = {
            "sequence": sequence,
            "urn": self.urn_generator.advertisement_urn(
                timber_id,
                sequence,
            ),
            "type": "others",
            "ref_material": registry["wood"]["urn"],
            "status": STATUS_LOCAL_ONLY,
            "created_at": now,
            "published_at": None,
        }

        registry["advertisements"].append(
            advertisement
        )

        registry["updated_at"] = now

        self._save(
            timber_id,
            registry,
        )

        return deepcopy(advertisement)

    def _save(
        self,
        timber_id: str,
        registry: dict[str, Any],
    ) -> None:
        """Validate and persist registry changes."""

        self._validate_registry(
            registry,
            timber_id,
        )

        path = self.registry_path(
            timber_id
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"CIRCULOOS registry missing: {path}"
            )

        _write_json_atomic(
            path,
            registry,
        )

    def set_publication_status(
        self,
        timber_id: str,
        status: str,
        advertisement_urn: str | None = None,
    ) -> dict[str, Any]:
        """Record an externally determined publication result.

        This method does not perform or verify publication.
        The publishing service must establish the result first.

        advertisement_urn=None targets the Wood entity.
        """

        if status not in PUBLICATION_STATUSES:
            raise ValueError(
                f"Invalid publication status: {status}"
            )

        registry = self.load(
            timber_id
        )

        if registry is None:
            raise FileNotFoundError(
                "CIRCULOOS registry has not been created."
            )

        if advertisement_urn is None:
            target = registry["wood"]

        else:
            target = next(
                (
                    ad
                    for ad in registry["advertisements"]
                    if ad["urn"] == advertisement_urn
                ),
                None,
            )

            if target is None:
                raise ValueError(
                    "Advertisement URN not found in registry."
                )

        now = _utc_now()

        target["status"] = status

        if status == STATUS_PUBLISHED:
            target["published_at"] = now

        elif status == STATUS_LOCAL_ONLY:
            target["published_at"] = None

        # On failure, retain any previous published_at
        # for historical reference.

        registry["updated_at"] = now

        self._save(
            timber_id,
            registry,
        )

        return deepcopy(registry)