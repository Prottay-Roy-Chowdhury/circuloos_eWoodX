"""Transport-independent agent identity model."""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable


@dataclass
class Agent:
    """
    Transport-independent identity and capability description
    for a distributed agent.
    """

    agent_id: str
    roles: list[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.agent_id = self._required_text(
            self.agent_id,
            "agent_id",
            lowercase=False,
        )

        self.roles = self._normalize_roles(
            self.roles
        )

        if not isinstance(
            self.metadata,
            dict,
        ):
            raise TypeError(
                "metadata must be a dictionary."
            )

    def has_role(
        self,
        role: str,
    ) -> bool:
        """
        Return True when this agent provides the given role.
        """

        normalized_role = self._required_text(
            role,
            "role",
        )

        return normalized_role in self.roles

    def can_handle(
        self,
        target: str,
    ) -> bool:
        """
        Return True when this agent can handle an action target.
        """

        return self.has_role(
            target
        )

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Return a JSON-serializable representation.
        """

        return {
            "agent_id": self.agent_id,
            "roles": list(
                self.roles
            ),
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> "Agent":
        """
        Create an Agent from a dictionary.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "data must be a dictionary."
            )

        return cls(
            agent_id=data.get(
                "agent_id"
            ),
            roles=list(
                data.get("roles")
                or []
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

    @classmethod
    def _normalize_roles(
        cls,
        roles: Iterable[Any],
    ) -> list[str]:
        if isinstance(
            roles,
            str,
        ):
            roles = [
                roles
            ]

        normalized = []

        for role in roles:
            role_name = cls._required_text(
                role,
                "role",
            )

            if role_name not in normalized:
                normalized.append(
                    role_name
                )

        return normalized