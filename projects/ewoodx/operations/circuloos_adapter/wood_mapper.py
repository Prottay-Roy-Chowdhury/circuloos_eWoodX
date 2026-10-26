"""Map existing eWoodX timber measurements to CIRCULOOS Wood.

The mapper:
- Resolves an existing timber using EntityManager.
- Reads measurements.json.
- Reuses the persistent Wood URN from the registry.
- Generates a normalized NGSI-LD Wood entity.
- Optionally writes circuloos_wood.json.

No Orion-LD requests or publication status changes occur.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from framework.workspace import EntityManager

from .entity_registry import CirculoosEntityRegistry


WOOD_PAYLOAD_FILE = "circuloos_wood.json"
MEASUREMENTS_FILE = "measurements.json"

WOOD_CONTEXT_URL = (
    "https://raw.githubusercontent.com/"
    "european-dynamics-rnd/CIRCULOOS_Data_model/"
    "main/material/wood/context.jsonld"
)

NGSILD_CORE_CONTEXT_URL = (
    "https://uri.etsi.org/ngsi-ld/v1/"
    "ngsi-ld-core-context-v1.8.jsonld"
)


def _property(
    value: Any,
    unit_code: str | None = None,
) -> dict[str, Any]:
    """Build a normalized NGSI-LD Property."""

    result = {
        "type": "Property",
        "value": value,
    }

    if unit_code is not None:
        result["unitCode"] = unit_code

    return result


def _positive_number(
    data: dict[str, Any],
    field: str,
) -> float | None:
    """Return a finite positive measurement, if present."""

    value = data.get(field)

    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ValueError(
            f"Measurement '{field}' must be numeric."
        )

    value = float(value)

    if not math.isfinite(value) or value <= 0:
        raise ValueError(
            f"Measurement '{field}' must be "
            "finite and greater than zero."
        )

    return value


def _save_json_atomic(
    path: Path,
    payload: list[dict[str, Any]],
) -> None:
    """Write the payload atomically."""

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
                ensure_ascii=False,
                indent=2,
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


class CirculoosWoodMapper:
    """Prepare Wood entities from existing eWoodX timber data."""

    def __init__(
        self,
        entity_manager: EntityManager,
        registry: CirculoosEntityRegistry | None = None,
        include_thickness: bool = False,
        include_context: bool = False,
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
                "registry must be a CirculoosEntityRegistry."
            )

        if self.registry.entity_manager is not entity_manager:
            raise ValueError(
                "Registry and mapper must use "
                "the same EntityManager instance."
            )

        self.include_thickness = include_thickness
        self.include_context = include_context

    def _load_measurements(
        self,
        timber_id: str,
    ) -> tuple[Path, dict[str, Any]]:
        """Locate and read existing timber measurements."""

        entity_root = self.registry._resolve_timber(
            timber_id
        )

        measurements_path = (
            entity_root / MEASUREMENTS_FILE
        )

        if not measurements_path.is_file():
            raise FileNotFoundError(
                f"Measurements file missing: "
                f"{measurements_path}"
            )

        with measurements_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            measurements = json.load(file)

        if not isinstance(measurements, dict):
            raise ValueError(
                "measurements.json must contain a JSON object."
            )

        measured_id = measurements.get("timber_id")

        if (
            measured_id is not None
            and measured_id != timber_id
        ):
            raise ValueError(
                "Measurement timber ID does not match "
                "the requested entity."
            )

        return entity_root, measurements

    def build(
        self,
        timber_id: str,
    ) -> list[dict[str, Any]]:
        """Build a Wood payload without writing a payload file."""

        timber_id = (
            self.registry.urn_generator
            .validate_timber_id(timber_id)
        )

        # Validate the local measurements before creating
        # a registry for an unmapped timber.
        _, measurements = self._load_measurements(
            timber_id
        )

        length = _positive_number(
            measurements,
            "length_mm",
        )

        width = _positive_number(
            measurements,
            "width_mm",
        )

        surface_area = _positive_number(
            measurements,
            "surface_area_mm2",
        )

        thickness = None

        if self.include_thickness:
            thickness = _positive_number(
                measurements,
                "timber_thickness_mm",
            )

        color = measurements.get(
            "color_hex"
        )

        if color is not None:
            if not isinstance(color, str):
                raise ValueError(
                    "color_hex must be a string."
                )

            color = color.strip()

            if not color:
                color = None

        # Create or reuse the persistent CIRCULOOS identity.
        registry_data = self.registry.ensure(
            timber_id
        )

        payload: dict[str, Any] = {
            "id": registry_data["wood"]["urn"],
            "type": "wood",
        }

        if length is not None:
            payload["length"] = _property(
                length,
                "MMT",
            )

        if width is not None:
            payload["width"] = _property(
                width,
                "MMT",
            )

        if thickness is not None:
            payload["thickness"] = _property(
                thickness,
                "MMT",
            )

        if surface_area is not None:
            payload["quantity"] = _property(
                surface_area / 1_000_000.0,
                "MTK",
            )

        if color is not None:
            payload["color"] = _property(
                color
            )

        if self.include_context:
            payload["@context"] = [
                WOOD_CONTEXT_URL,
                NGSILD_CORE_CONTEXT_URL,
            ]

        return [payload]

    def save(
        self,
        timber_id: str,
    ) -> Path:
        """Generate and save the CIRCULOOS Wood JSON array."""

        payload = self.build(timber_id)

        entity_root = self.registry._resolve_timber(
            timber_id
        )

        output_path = entity_root / WOOD_PAYLOAD_FILE

        _save_json_atomic(
            output_path,
            payload,
        )

        return output_path