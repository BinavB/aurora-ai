"""The agentic pipeline: Intent → Plan → Execute → Verify → Learn.

Most agents collapse to ``prompt → LLM → answer``. This orchestrator instead
runs a disciplined loop: understand the request, plan it, execute the plan with
tools, verify the result against the objective, and persist what was learned.

Verification is enforced with an **escalating retry strategy**: a failed
verification does not simply re-run the same approach — it escalates (implement →
debug → re-architect) and, when a router is available, reassigns to a model
stronger at the skill the next strategy needs. If every strategy fails, the run
ends as ``NEEDS_INPUT`` rather than a false success.
"""

from __future__ import annotations

from aurora.app.core.logging import get_logger
from aurora.app.router.models import RoutingRequest, TaskKind
from aurora.app.router.router import Router
from aurora.app.services.execution_service import ExecutionService
from aurora.app.services.memory_service import MemoryService
from aurora.app.services.models import PipelineAttempt, PipelineResult, TaskSpec
from aurora.app.services.planning_service import PlanningService
from aurora.app.services.task_service import TaskService
from aurora.app.services.verification_service import VerificationService

_logger = get_logger("services.pipeline")

# Escalation ladder: (strategy label, directive added to the task, skill to
# reassign toward on this attempt).
_STRATEGIES: tuple[tuple[str, str, str], ...] = (
    ("coder", "", "coding"),
    (
        "debugger",
        "The previous attempt failed verification. Diagnose the root cause "
        "before changing anything, then fix it.",
        "reasoning",
    ),
    (
        "architect+coder",
        "Previous attempts failed. Reconsider the approach at an architectural "
        "level, then implement the corrected design.",
        "reasoning",
    ),
)


class AgentPipeline:
    """Sequence the five stages, escalating strategy until verified or stuck."""

    def __init__(
        self,
        task: TaskService,
        planning: PlanningService,
        execution: ExecutionService,
        verification: VerificationService,
        memory: MemoryService,
        router: Router | None = None,
    ) -> None:
        self._task = task
        self._planning = planning
        self._execution = execution
        self._verification = verification
        self._memory = memory
        self._router = router

    async def run(
        self,
        request: str,
        workspace: str,
        *,
        max_steps: int = 12,
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> PipelineResult:
        """Run intent → plan → (execute → verify) with retry → learn."""
        routing = {"offline": offline, "prefer_provider": prefer_provider}
        spec = self._task.understand(request)
        plan_result = await self._planning.plan(
            spec.objective, workspace, prefer_model=prefer_model, **routing
        )

        attempts: list[PipelineAttempt] = []
        execution = verification = None
        for index, (strategy, directive, skill) in enumerate(_STRATEGIES):
            attempt_spec = self._with_directive(spec, directive)
            model = self._model_for(index, skill, offline, prefer_model)
            execution = await self._execution.execute(
                attempt_spec,
                plan_result.plan,
                workspace,
                max_steps=max_steps,
                prefer_model=model,
                **routing,
            )
            verification = await self._verification.verify(
                attempt_spec, execution, prefer_model=model, **routing
            )
            attempts.append(
                PipelineAttempt(
                    strategy=strategy,
                    provider=execution.provider,
                    model=execution.model,
                    verified=verification.passed,
                )
            )
            if verification.passed:
                break

        memory = await self._memory.learn(spec, execution, verification)
        status = "COMPLETE" if verification.passed else "NEEDS_INPUT"
        _logger.info(
            "pipeline_complete",
            extra={"status": status, "attempts": len(attempts)},
        )
        return PipelineResult(
            objective=spec.objective,
            intent=spec.intent,
            plan=plan_result.plan,
            execution=execution,
            verification=verification,
            memory=memory,
            status=status,
            attempts=attempts,
        )

    @staticmethod
    def _with_directive(spec: TaskSpec, directive: str) -> TaskSpec:
        if not directive:
            return spec
        return spec.model_copy(update={"constraints": [*spec.constraints, directive]})

    def _model_for(
        self, attempt: int, skill: str, offline: bool, prefer_model: str | None
    ) -> str | None:
        """Reassign to a skill-appropriate model on escalated attempts."""
        if attempt == 0 or prefer_model or self._router is None:
            return prefer_model
        request = RoutingRequest(
            task="retry", kind=TaskKind.IMPLEMENT, needs_tools=True, offline=offline
        )
        return self._router.strongest_model(request, skill)
