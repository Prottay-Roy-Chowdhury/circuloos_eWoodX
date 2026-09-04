"""Transport-independent distributed action model."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict
from uuid import uuid4


class ActionStatus(str, Enum):
    """
    Lifecycle states of a distributed action.
    """

    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Action:
    """
    Transport-independent description of work intended
    for a distributed agent.

    The action contains no knowledge of TCP, ports,
    sockets, files, or deployment configuration.
    """

    action: str
    target: str

    payload: Dict[str, Any] = field(
        default_factory=dict
    )

    action_id: str = field(
        default_factory=lambda: str(
            uuid4()
        )
    )

    status: ActionStatus = (
        ActionStatus.PENDING
    )

    claimed_by: str | None = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.action = self._required_text(
            self.action,
            "action",
        )

        self.target = self._required_text(
            self.target,
            "target",
        )

        self.action_id = self._required_text(
            self.action_id,
            "action_id",
            lowercase=False,
        )

        if not isinstance(
            self.payload,
            dict,
        ):
            raise TypeError(
                "payload must be a dictionary."
            )

        if not isinstance(
            self.metadata,
            dict,
        ):
            raise TypeError(
                "metadata must be a dictionary."
            )

        if not isinstance(
            self.status,
            ActionStatus,
        ):
            self.status = ActionStatus(
                str(self.status).strip().lower()
            )

        if self.claimed_by is not None:
            self.claimed_by = (
                self._required_text(
                    self.claimed_by,
                    "claimed_by",
                )
            )

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Return a JSON-serializable representation.
        """

        return {
            "action_id": self.action_id,
            "action": self.action,
            "target": self.target,
            "status": self.status.value,
            "claimed_by": self.claimed_by,
            "payload": dict(
                self.payload
            ),
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> "Action":
        """
        Create an Action from a dictionary.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "data must be a dictionary."
            )

        return cls(
            action=data.get(
                "action"
            ),
            target=data.get(
                "target"
            ),
            payload=dict(
                data.get("payload")
                or {}
            ),
            action_id=data.get(
                "action_id"
            )
            or str(uuid4()),
            status=data.get(
                "status"
            )
            or ActionStatus.PENDING,
            claimed_by=data.get(
                "claimed_by"
            ),
            metadata=dict(
                data.get("metadata")
                or {}
            ),
        )

    @staticmethod
    def _required_text(
        value: Any,
        field_name: str,
        lowercase: bool = True,
    ) -> str:
        normalized = str(
            value or ""
        ).strip()

        if lowercase:
            normalized = (
                normalized.lower()
            )

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return normalized