"""Local durable action storage for an agent."""

import json
from pathlib import Path
from typing import Any, Dict, Union

from framework.communication.core import (
    Action,
    Agent,
)


PathLike = Union[str, Path]


class AgentActionStore:
    """
    Persist the current local action state for one agent.

    This store is agent-local and does not represent the
    authoritative shared action lifecycle.
    """

    def __init__(
        self,
        root: PathLike,
        agent: Agent,
    ):
        if not isinstance(
            agent,
            Agent,
        ):
            raise TypeError(
                "agent must be an Agent."
            )

        self.root = Path(
            root
        ).resolve()

        self.agent = agent

    def save(
        self,
        action: Action,
    ) -> Path:
        """
        Persist an action locally for this agent.
        """

        if not isinstance(
            action,
            Action,
        ):
            raise TypeError(
                "action must be an Action."
            )

        if (
            action.claimed_by
            != self.agent.agent_id
        ):
            raise RuntimeError(
                "Action is not claimed by this agent."
            )

        active_data = self.find_active()

        if active_data is not None:
            active_action = active_data.get(
                "action"
            )

            if not isinstance(
                active_action,
                dict,
            ):
                raise RuntimeError(
                    "Invalid active local action record."
                )

            active_action_id = str(
                active_action.get(
                    "action_id",
                    "",
                )
            ).strip()

            if (
                active_action_id
                == action.action_id
            ):
                return self._get_path(
                    action.action_id
                )

            raise RuntimeError(
                "Another active local action already exists: "
                f"{active_action_id}."
            )

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "agent_id": self.agent.agent_id,
            "action": action.to_dict(),
            "consumed": False,
        }

        path = self._get_path(
            action.action_id
        )

        self._write_json(
            path,
            data,
        )

        return path

    def load(
        self,
        action_id: str,
    ) -> Dict[str, Any]:
        """
        Load local state for an action.
        """

        path = self._get_path(
            action_id
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"Local action not found: {action_id}"
            )

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(
                file
            )

    def mark_consumed(
        self,
        action_id: str,
    ) -> Dict[str, Any]:
        """
        Mark the local action as consumed.
        """

        data = self.load(
            action_id
        )

        if data.get(
            "agent_id"
        ) != self.agent.agent_id:
            raise RuntimeError(
                "Local action belongs to another agent."
            )

        data["consumed"] = True

        self._write_json(
            self._get_path(
                action_id
            ),
            data,
        )

        return data

    def is_consumed(
        self,
        action_id: str,
    ) -> bool:
        """
        Return whether the local action was consumed.
        """

        data = self.load(
            action_id
        )

        return bool(
            data.get(
                "consumed",
                False,
            )
        )

    def find_unconsumed(
        self,
    ) -> Dict[str, Any] | None:
        """
        Return the current unconsumed local action.

        Returns None when no unconsumed action exists.
        """

        if not self.root.is_dir():
            return None

        for path in sorted(
            self.root.glob("*.json")
        ):
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(
                    file
                )

            if (
                data.get("agent_id")
                != self.agent.agent_id
            ):
                continue

            if not bool(
                data.get(
                    "consumed",
                    False,
                )
            ):
                return data

        return None

    def find_active(
        self,
    ) -> Dict[str, Any] | None:
        """
        Return the current active local action.

        An action remains active even after it has been
        consumed locally. It remains active until the local
        lifecycle later marks or clears it as terminal.
        """

        if not self.root.is_dir():
            return None

        for path in sorted(
            self.root.glob("*.json")
        ):
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(
                    file
                )

            if (
                data.get("agent_id")
                != self.agent.agent_id
            ):
                continue

            return data

        return None

    def exists(
        self,
        action_id: str,
    ) -> bool:
        return self._get_path(
            action_id
        ).is_file()

    def delete(
        self,
        action_id: str,
    ) -> bool:
        path = self._get_path(
            action_id
        )

        if not path.is_file():
            return False

        path.unlink()

        return True

    def _write_json(
        self,
        path: Path,
        data: Dict[str, Any],
    ) -> None:
        temporary_path = path.with_suffix(
            path.suffix + ".tmp"
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
            path
        )

    def _get_path(
        self,
        action_id: str,
    ) -> Path:
        normalized_action_id = str(
            action_id or ""
        ).strip()

        if not normalized_action_id:
            raise ValueError(
                "action_id cannot be empty."
            )

        return self.root / (
            f"{normalized_action_id}.json"
        )