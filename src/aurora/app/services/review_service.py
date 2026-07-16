"""Review service: coordinate a code review."""

from __future__ import annotations

from aurora.app.agents.models import ReviewInput
from aurora.app.agents.reviewer import ReviewerAgent
from aurora.app.router.models import RoutingRequest
from aurora.app.router.router import Router
from aurora.app.services.base import RoutedService
from aurora.app.services.factory import ProviderFactory
from aurora.app.services.models import ReviewOutcome


class ReviewService(RoutedService):
    """Route and run the reviewer agent over supplied code."""

    def __init__(self, router: Router, factory: ProviderFactory) -> None:
        super().__init__(router, factory)

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
            offline=offline,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        async with self._routed(request) as (decision, provider):
            result = await ReviewerAgent(provider, decision.model).run(
                ReviewInput(code=code, focus=focus)
            )
        return ReviewOutcome(
            provider=decision.provider, model=decision.model, result=result
        )
