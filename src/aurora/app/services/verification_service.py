"""Verification service — the Verify stage of the agentic pipeline.

Asks a model to judge whether the execution actually satisfied the objective,
returning a structured PASS/FAIL verdict with concrete issues. This is what
separates a real agent from "prompt → answer": the work is checked before it is
accepted, and the issues feed the Learn stage.
"""

from __future__ import annotations

from aurora.app.agents.llm import complete, lead_system, parse_list_items, user
from aurora.app.router.models import RoutingDecision, RoutingRequest, TaskKind
from aurora.app.services.base import RoutedService
from aurora.app.services.models import AgentResult, TaskSpec, VerificationReport

_SYSTEM = (
    "You are a strict verification reviewer. Decide whether the work satisfies "
    "the objective. Reply on the first line with exactly PASS or FAIL, then list "
    "any issues as '- ' bullet points (none if it passed)."
)


class VerificationService(RoutedService):
    """Verify stage: judge the execution against the objective."""

    async def verify(
        self,
        spec: TaskSpec,
        execution: AgentResult,
        *,
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> VerificationReport:
        """Return a PASS/FAIL verdict on whether ``execution`` met the objective."""
        request = RoutingRequest(
            task="verification",
            kind=TaskKind.REVIEW,
            offline=offline,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        report = execution.report
        prompt = (
            f"Objective:\n{spec.objective}\n\n"
            f"Agent completed: {report.completed}\n"
            f"Agent's final answer:\n{report.answer}\n\n"
            "Did the work satisfy the objective?"
        )

        async def work(decision: RoutingDecision, provider) -> str:
            return await complete(
                provider,
                decision.model,
                [lead_system(self._system_prompt, _SYSTEM), user(prompt)],
                max_tokens=600,
            )

        decision, text = await self._attempt(request, work)
        return self._parse(decision, text)

    @staticmethod
    def _parse(decision: RoutingDecision, text: str) -> VerificationReport:
        """Read the PASS/FAIL verdict and any issue bullets from the reply."""
        stripped = text.strip()
        first_line = stripped.splitlines()[0] if stripped else ""
        passed = "pass" in first_line.lower() and "fail" not in first_line.lower()
        issues = [i for i in parse_list_items(stripped) if i != first_line]
        summary = first_line or ("passed" if passed else "failed")
        return VerificationReport(
            provider=decision.provider,
            model=decision.model,
            passed=passed,
            summary=summary,
            issues=[] if passed else issues,
        )
