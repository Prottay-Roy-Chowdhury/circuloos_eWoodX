"""Persistent storage for distributed actions."""

import json
from pathlib import Path
from typing import Union

from framework.communication.core import (
    Action,
    ActionStatus,
    Agent,
)


PathLike = Union[str, Path]


class ActionStore:
    """
    Persist distributed actions as JSON files.

    Each action is stored using its action_id:

        <root>/
            <action_id>.json
    """

    def __init__(
        self,
        root: PathLike,
    ):
        self.root = Path(
            root
        ).resolve()

    def save(
        self,
        action: Action,
    ) -> Path:
        """
        Persist an action to disk.
        """

        if not isinstance(
            action,
            Action,
        ):
            raise TypeError(
                "action must be an Action."
            )

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = self._get_path(
            action.action_id
        )

        temporary_path = path.with_suffix(
            path.suffix + ".tmp"
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                action.to_dict(),
                file,
                ensure_ascii=False,
                indent=2,
            )

        temporary_path.replace(
            path
        )

        return path

    def load(
        self,
        action_id: str,
    ) -> Action:
        """
        Load an action from disk.
        """

        path = self._get_path(
            action_id
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"Action not found: {action_id}"
            )

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

        return Action.from_dict(
            data
        )

    def exists(
        self,
        action_id: str,
    ) -> bool:
        """
        Return True if the action exists.
        """

        return self._get_path(
            action_id
        ).is_file()

    def delete(
        self,
        action_id: str,
    ) -> bool:
        """
        Delete an action.

        Returns True if a file was deleted.
        """

        path = self._get_path(
            action_id
        )

        if not path.is_file():
            return False

        path.unlink()

        return True

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

    def claim(
        self,
        action_id: str,
        agent: Agent,
    ) -> Action:
        """
        Claim a pending action for an eligible agent.
        """

        if not isinstance(
            agent,
            Agent,
        ):
            raise TypeError(
                "agent must be an Agent."
            )

        action = self.load(
            action_id
        )

        if (
            action.status
            != ActionStatus.PENDING
        ):
            raise RuntimeError(
                "Only pending actions can be claimed."
            )

        if not agent.can_handle(
            action.target
        ):
            raise RuntimeError(
                f"Agent '{agent.agent_id}' "
                f"cannot handle target "
                f"'{action.target}'."
            )

        if action.claimed_by is not None:
            raise RuntimeError(
                "Action is already claimed."
            )

        action.status = (
            ActionStatus.CLAIMED
        )

        action.claimed_by = (
            agent.agent_id
        )

        self.save(
            action
        )

        return action

    def mark_running(
        self,
        action_id: str,
        agent: Agent,
    ) -> Action:
        action = self.load(
            action_id
        )

        if (
            action.status
            != ActionStatus.CLAIMED
        ):
            raise RuntimeError(
                "Only claimed actions can become running."
            )

        if (
            action.claimed_by
            != agent.agent_id
        ):
            raise RuntimeError(
                "Action is claimed by another agent."
            )

        action.status = (
            ActionStatus.RUNNING
        )

        self.save(
            action
        )

        return action

    def mark_terminal(
        self,
        action_id: str,
        agent: Agent,
        status: ActionStatus,
    ) -> Action:
        if status not in {
            ActionStatus.COMPLETED,
            ActionStatus.FAILED,
            ActionStatus.CANCELLED,
        }:
            raise ValueError(
                "status must be a terminal ActionStatus."
            )

        action = self.load(
            action_id
        )

        if (
            action.claimed_by
            != agent.agent_id
        ):
            raise RuntimeError(
                "Action is claimed by another agent."
            )

        if (
            action.status
            != ActionStatus.RUNNING
        ):
            raise RuntimeError(
                "Only running actions can become terminal."
            )

        action.status = status

        self.save(
            action
        )

        return action

    def list_actions(
        self,
    ) -> list[Action]:
        """
        Load all stored actions.
        """

        if not self.root.is_dir():
            return []

        actions = []

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

            actions.append(
                Action.from_dict(
                    data
                )
            )

        return actions

    def find_pending(
        self,
        targets: list[str] | None = None,
    ) -> list[Action]:
        """
        Find pending actions, optionally filtered by target.
        """

        normalized_targets = None

        if targets is not None:
            normalized_targets = {
                str(target).strip().lower()
                for target in targets
                if str(target).strip()
            }

        pending_actions = []

        for action in self.list_actions():
            if (
                action.status
                != ActionStatus.PENDING
            ):
                continue

            if (
                normalized_targets is not None
                and action.target
                not in normalized_targets
            ):
                continue

            pending_actions.append(
                action
            )

        return pending_actions