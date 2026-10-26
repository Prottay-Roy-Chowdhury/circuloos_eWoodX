"""CIRCULOOS NGSI-LD URN generation for eWoodX.

This module converts existing eWoodX timber identifiers into
CIRCULOOS entity identifiers.

It does not:
- Allocate local timber IDs.
- Modify the generic EntityManager.
- Create or update entity files.
- Communicate with Orion-LD.
- Track publication status.

Persistent allocation and reuse will be handled separately
by entity_registry.py.
"""

from __future__ import annotations

import re

from projects.ewoodx.config.entity import (
    TIMBER_ID_PREFIX,
)


# -------------------------------------------------------------
# CIRCULOOS identity configuration
# -------------------------------------------------------------

URN_PREFIX = "urn:ngsi-ld"

EWOODX_NAMESPACE = "ewoodx"

WOOD_URN_TYPE = "wood"

# Current RAMP advertisement entity type used in our tests.
RAMP_AD_URN_TYPE = "others"

ADVERTISEMENT_PREFIX = "AD"
ADVERTISEMENT_SEQUENCE_WIDTH = 3
ADVERTISEMENT_SEQUENCE_MAX = 999999


# -------------------------------------------------------------
# Validation
# -------------------------------------------------------------

_TIMBER_ID_PATTERN = re.compile(
    rf"^{re.escape(TIMBER_ID_PREFIX)}-[0-9]{{4,6}}-[A-Z0-9]{{3}}$"
)


class CirculoosURNGenerator:
    """Generate eWoodX-specific NGSI-LD entity identifiers."""

    def __init__(
        self,
        namespace: str = EWOODX_NAMESPACE,
    ) -> None:

        if not isinstance(namespace, str):
            raise TypeError(
                "namespace must be a string."
            )

        namespace = namespace.strip()

        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]*",
            namespace,
        ):
            raise ValueError(
                "Invalid CIRCULOOS namespace."
            )

        self.namespace = namespace

    @staticmethod
    def validate_timber_id(
        timber_id: str,
    ) -> str:
        """Validate an existing eWoodX timber identifier."""

        if not isinstance(timber_id, str):
            raise TypeError(
                "timber_id must be a string."
            )

        timber_id = timber_id.strip()

        if not _TIMBER_ID_PATTERN.fullmatch(timber_id):
            raise ValueError(
                f"Invalid eWoodX timber ID: {timber_id}"
            )

        return timber_id

    @staticmethod
    def validate_ad_sequence(
        sequence: int,
    ) -> int:
        """Validate an advertisement sequence number."""

        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
        ):
            raise TypeError(
                "Advertisement sequence must be an integer."
            )

        if not (
            1 <= sequence <= ADVERTISEMENT_SEQUENCE_MAX
        ):
            raise ValueError(
                "Advertisement sequence is out of range."
            )

        return sequence

    def wood_urn(
        self,
        timber_id: str,
    ) -> str:
        """Generate the Wood URN for an existing timber ID."""

        timber_id = self.validate_timber_id(
            timber_id
        )

        return (
            f"{URN_PREFIX}:"
            f"{WOOD_URN_TYPE}:"
            f"{self.namespace}-{timber_id}"
        )

    def advertisement_urn(
        self,
        timber_id: str,
        sequence: int = 1,
    ) -> str:
        """Generate a RAMP advertisement URN.

        Sequence allocation is the registry's responsibility.
        This method only formats an explicitly supplied number.
        """

        timber_id = self.validate_timber_id(
            timber_id
        )

        sequence = self.validate_ad_sequence(
            sequence
        )

        advertisement_id = (
            f"{ADVERTISEMENT_PREFIX}-"
            f"{sequence:0{ADVERTISEMENT_SEQUENCE_WIDTH}d}"
        )

        return (
            f"{URN_PREFIX}:"
            f"{RAMP_AD_URN_TYPE}:"
            f"{self.namespace}-{timber_id}-{advertisement_id}"
        )
