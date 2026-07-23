"""Execution service — the Execute stage of the agentic pipeline.

Carries out an approved plan by driving the autonomous agent. It composes
:class:`AutonomousService` (rather than re-implementing the tool loop) and simply
frames the objective and plan as the agent's task, so there is one execution
engine in the system, not two.
"""

from __future__ import annotations

from aurora.app.agents.models import Plan
from aurora.app.services.autonomous_service import AutonomousService
from aurora.app.services.models import AgentResult, TaskSpec


class ExecutionService:
    """Execute stage: run the plan with the autonomous, tool-using agent."""

    def __init__(self, autonomous: AutonomousService) -> None:
        self._autonomous = autonomous

    async def execute(
        self,
        spec: TaskSpec,
        plan: Plan,
        workspace: str,
        *,
        max_steps: int = 12,
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> AgentResult:
        """Run ``plan`` toward ``spec.objective`` in ``workspace``."""
        return await self._autonomous.run(
            self._render(spec, plan),
            workspace,
            max_steps=max_steps,
            offline=offline,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )

    @staticmethod
    def _render(spec: TaskSpec, plan: Plan) -> str:
        """Frame the objective and plan as a single instruction for the agent."""
        steps = "\n".join(f"{step.index}. {step.description}" for step in plan.steps)
        instruction = f"Objective: {spec.objective}"
        if steps:
            instruction += f"\n\nApproved plan:\n{steps}"
        if spec.constraints:
            instruction += "\n\nConstraints:\n" + "\n".join(
                f"- {c}" for c in spec.constraints
            )
        return instruction + "\n\nCarry out the plan step by step using the tools."
