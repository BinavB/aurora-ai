"""Review service: coordinate a code review."""

from __future__ import annotations

from aurora.app.agents.models import ReviewInput
from aurora.app.agents.reviewer import ReviewerAgent
from aurora.app.router.models import RoutingRequest, TaskKind
from aurora.app.services.base import RoutedService
from aurora.app.services.models import ReviewOutcome


class ReviewService(RoutedService):
    """Route and run the reviewer agent over supplied code."""

    async def review(
        self,
        code: str,
        focus: str = "correctness, clarity, and bugs",
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> ReviewOutcome:
        """Review ``code`` and return structured findings."""
        request = RoutingRequest(
            task="code review",
            kind=TaskKind.REVIEW,
            offline=offline,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )

        async def work(decision, provider):
            return await ReviewerAgent(provider, decision.model, self._system_prompt).run(
                ReviewInput(code=code, focus=focus)
            )

        decision, result = await self._attempt(request, work)
        return ReviewOutcome(
            provider=decision.provider, model=decision.model, result=result
        )
