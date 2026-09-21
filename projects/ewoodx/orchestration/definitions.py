"""eWoodX project orchestration definitions."""

from framework.orchestration import (
    OrchestrationDefinition,
    OrchestrationStep,
)


SENSING_ORCHESTRATION = OrchestrationDefinition(
    name="sensing",
    steps=[
        OrchestrationStep(
            step_id="sense_timber",
            action="sense_timber",
            target="sensing",
        ),
    ],
)