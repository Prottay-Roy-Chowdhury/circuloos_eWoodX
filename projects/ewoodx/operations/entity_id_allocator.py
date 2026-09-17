"""Persistent entity ID allocation for eWoodX."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from framework.workspace import EntityManager

from projects.ewoodx.config import (
    ENTITY_ID_RANDOM_ALPHABET,
    ENTITY_ID_RANDOM_LENGTH,
    ENTITY_ID_SEQUENCE_MAX_VALUE,
    ENTITY_ID_SEQUENCE_MIN_WIDTH,
)


COUNTER_FILE = "entity_counters.json"


class EWoodXEntityIdAllocator:
    """
    Allocate persistent project-specific entity IDs.

    The framework owns entity existence and persistence.
    eWoodX owns ID naming and counter semantics.
    """

    def __init__(
        self,
        entity_manager: EntityManager,
    ) -> None:

        if not isinstance(
            entity_manager,
            EntityManager,
        ):
            raise TypeError(
                "entity_manager must be an "
                "EntityManager instance."
            )

        self.entity_manager = entity_manager

        self.counter_path = (
            self.entity_manager.workspace.root
            / "project"
            / COUNTER_FILE
        )

        self.counter_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _load_counters(
        self,
    ) -> dict[str, int]:
        """
        Load persistent project entity counters.
        """

        if not self.counter_path.exists():
            return {}

        with self.counter_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Entity counter file must contain "
                "a JSON object."
            )

        counters = data.get(
            "entity_counters",
            {},
        )

        if not isinstance(
            counters,
            dict,
        ):
            raise ValueError(
                "entity_counters must be a JSON object."
            )

        validated: dict[str, int] = {}

        for entity_type, counter in counters.items():

            if (
                not isinstance(entity_type, str)
                or not entity_type.strip()
            ):
                raise ValueError(
                    "Entity counter names must be "
                    "non-empty strings."
                )

            if (
                not isinstance(counter, int)
                or isinstance(counter, bool)
                or counter < 0
            ):
                raise ValueError(
                    f"Invalid counter for "
                    f"'{entity_type}'."
                )

            validated[
                entity_type.strip()
            ] = counter

        return validated

    def _save_counters(
        self,
        counters: dict[str, int],
    ) -> None:
        """
        Persist entity counters atomically.
        """

        data = {
            "entity_counters": counters,
        }

        temporary_path = (
            self.counter_path.with_suffix(
                self.counter_path.suffix + ".tmp"
            )
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        temporary_path.replace(
            self.counter_path
        )

    def _random_token(
        self,
    ) -> str:
        """
        Generate the random base-36 component.
        """

        return "".join(
            secrets.choice(
                ENTITY_ID_RANDOM_ALPHABET
            )
            for _ in range(
                ENTITY_ID_RANDOM_LENGTH
            )
        )

    def allocate(
        self,
        entity_type: str,
        prefix: str,
    ) -> str:
        """
        Allocate the next project entity ID.

        Example:
            T-0001-K7M
        """

        if not isinstance(
            entity_type,
            str,
        ):
            raise TypeError(
                "entity_type must be a string."
            )

        entity_type = entity_type.strip()

        if not entity_type:
            raise ValueError(
                "entity_type cannot be empty."
            )

        if not isinstance(
            prefix,
            str,
        ):
            raise TypeError(
                "prefix must be a string."
            )

        prefix = prefix.strip().upper()

        if not prefix:
            raise ValueError(
                "prefix cannot be empty."
            )

        counters = self._load_counters()

        current_counter = counters.get(
            entity_type,
            0,
        )

        next_counter = (
            current_counter + 1
        )

        if (
            next_counter
            > ENTITY_ID_SEQUENCE_MAX_VALUE
        ):
            raise RuntimeError(
                f"Entity ID sequence limit reached "
                f"for '{entity_type}'."
            )

        sequence = str(
            next_counter
        ).zfill(
            ENTITY_ID_SEQUENCE_MIN_WIDTH
        )

        while True:

            random_token = (
                self._random_token()
            )

            candidate_id = (
                f"{prefix}-"
                f"{sequence}-"
                f"{random_token}"
            )

            if not self.entity_manager.exists(
                candidate_id
            ):
                break

        counters[
            entity_type
        ] = next_counter

        self._save_counters(
            counters
        )

        return candidate_id