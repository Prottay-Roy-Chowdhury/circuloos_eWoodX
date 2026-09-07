"""Reusable sequential orchestration definition."""

from framework.orchestration.step import (
    OrchestrationStep,
)


class OrchestrationDefinition:
    """
    Define an ordered sequence of orchestration steps.

    The definition describes orchestration structure only.

    It does not create actions, persist state,
    communicate with agents, or execute work.
    """

    def __init__(
        self,
        name: str,
        steps: list[OrchestrationStep],
    ):
        normalized_name = str(
            name or ""
        ).strip().lower()

        if not normalized_name:
            raise ValueError(
                "name cannot be empty."
            )

        if not isinstance(
            steps,
            list,
        ):
            raise TypeError(
                "steps must be a list."
            )

        if not steps:
            raise ValueError(
                "steps cannot be empty."
            )

        for step in steps:
            if not isinstance(
                step,
                OrchestrationStep,
            ):
                raise TypeError(
                    "Each orchestration step must be "
                    "an OrchestrationStep."
                )

        step_ids = [
            step.step_id
            for step in steps
        ]

        if (
            len(step_ids)
            != len(set(step_ids))
        ):
            raise ValueError(
                "Orchestration step_id values "
                "must be unique."
            )

        self.name = (
            normalized_name
        )

        self.steps = list(
            steps
        )

    def get_step(
        self,
        index: int,
    ) -> OrchestrationStep:
        """
        Return an orchestration step by index.
        """

        if not isinstance(
            index,
            int,
        ):
            raise TypeError(
                "index must be an integer."
            )

        if (
            index < 0
            or index >= len(self.steps)
        ):
            raise IndexError(
                "index is outside the "
                "orchestration step range."
            )

        return self.steps[
            index
        ]

    def get_next_step(
        self,
        index: int,
    ) -> OrchestrationStep | None:
        """
        Return the step after the supplied index.

        Returns None when the orchestration has finished.
        """

        if not isinstance(
            index,
            int,
        ):
            raise TypeError(
                "index must be an integer."
            )

        if (
            index < 0
            or index >= len(self.steps)
        ):
            raise IndexError(
                "index is outside the "
                "orchestration step range."
            )

        next_index = (
            index + 1
        )

        if (
            next_index
            >= len(self.steps)
        ):
            return None

        return self.steps[
            next_index
        ]

    def __len__(
        self,
    ) -> int:
        return len(
            self.steps
        )