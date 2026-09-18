"""Entry allocation for eWoodX."""

from __future__ import annotations

from datetime import datetime

from framework.workspace import (
    EntryManager,
)

from projects.ewoodx.config import (
    ENTRY_DATE_FORMAT,
    ENTRY_NAME_PREFIX,
)


class EWoodXEntryAllocator:
    """
    Allocate project-specific entry names.

    The framework owns entry persistence.
    eWoodX owns entry naming semantics.

    Entry numbering is local to each domain.
    """

    def __init__(
        self,
        entry_manager: EntryManager,
    ) -> None:

        if not isinstance(
            entry_manager,
            EntryManager,
        ):
            raise TypeError(
                "entry_manager must be an "
                "EntryManager instance."
            )

        self.entry_manager = entry_manager

    def _next_sequence(
        self,
    ) -> int:
        """
        Determine the next sequence number from
        the managed entries in this domain.
        """

        highest_sequence = 0

        prefix = (
            f"{ENTRY_NAME_PREFIX}_"
        )

        for entry in (
            self.entry_manager.list_entries()
        ):

            entry_name = (
                entry.entry_name
            )

            if not entry_name.startswith(
                prefix
            ):
                continue

            remainder = (
                entry_name[
                    len(prefix):
                ]
            )

            parts = (
                remainder.split(
                    "_",
                    1,
                )
            )

            if len(parts) != 2:
                continue

            sequence_text = parts[0]

            if not sequence_text.isdigit():
                continue

            sequence = int(
                sequence_text
            )

            highest_sequence = max(
                highest_sequence,
                sequence,
            )

        return (
            highest_sequence + 1
        )
    
    def latest_entry(
        self,
    ):
        """
        Return the managed eWoodX entry with the
        highest sequence number.

        Returns None when no matching eWoodX
        entries exist.
        """

        latest_entry = None
        highest_sequence = 0

        prefix = (
            f"{ENTRY_NAME_PREFIX}_"
        )

        for entry in (
            self.entry_manager.list_entries()
        ):

            entry_name = (
                entry.entry_name
            )

            if not entry_name.startswith(
                prefix
            ):
                continue

            remainder = (
                entry_name[
                    len(prefix):
                ]
            )

            parts = (
                remainder.split(
                    "_",
                    1,
                )
            )

            if len(parts) != 2:
                continue

            sequence_text = (
                parts[0]
            )

            if not sequence_text.isdigit():
                continue

            sequence = int(
                sequence_text
            )

            if sequence > highest_sequence:

                highest_sequence = (
                    sequence
                )

                latest_entry = (
                    entry
                )

        return latest_entry

    def allocate(
        self,
    ) -> str:
        """
        Allocate the next entry name for
        the current domain.

        Example:
            day_1_20260918
        """

        sequence = (
            self._next_sequence()
        )

        date_text = (
            datetime.now()
            .strftime(
                ENTRY_DATE_FORMAT
            )
        )

        entry_name = (
            f"{ENTRY_NAME_PREFIX}_"
            f"{sequence}_"
            f"{date_text}"
        )

        if self.entry_manager.exists(
            entry_name
        ):
            raise RuntimeError(
                "Allocated entry already exists: "
                f"{entry_name}"
            )

        return entry_name