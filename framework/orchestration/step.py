"""Reusable orchestration step definition."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class OrchestrationStep:
    """
    Describe one step in a project orchestration.

    A orchestration step defines:

        - a unique step identifier
        - the action to create
        - the agent role that can execute it
        - optional default payload data

    The step contains no communication,
    transport, storage, or execution logic.
    """

    step_id: str
    action: str
    target: str

    payload: Dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        step_id = self._required_text(
            self.step_id,
            "step_id",
        )

        action = self._required_text(
            self.action,
            "action",
        )

        target = self._required_text(
            self.target,
            "target",
        )

        if not isinstance(
            self.payload,
            dict,
        ):
            raise TypeError(
                "payload must be a dictionary."
            )

        object.__setattr__(
            self,
            "step_id",
            step_id,
        )

        object.__setattr__(
            self,
            "action",
            action,
        )

        object.__setattr__(
            self,
            "target",
            target,
        )

        object.__setattr__(
            self,
            "payload",
            dict(
                self.payload
            ),
        )

    @staticmethod
    def _required_text(
        value: Any,
        field_name: str,
    ) -> str:
        normalized = str(
            value or ""
        ).strip().lower()

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return normalized