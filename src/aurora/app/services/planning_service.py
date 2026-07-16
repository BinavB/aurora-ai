"""Planning service: build context, then produce a plan."""

from __future__ import annotations

from aurora.app.agents.context_builder import ContextBuilderAgent
from aurora.app.agents.models import PlannerInput
from aurora.app.agents.planner import PlannerAgent
from aurora.app.context.engine import ContextEngine
from aurora.app.context.models import ContextRequest
from aurora.app.router.models import RoutingRequest
from aurora.app.router.router import Router
from aurora.app.services.base import RoutedService
from aurora.app.services.factory import ProviderFactory
from aurora.app.services.models import PlanResult
from aurora.app.tools.filesystem import filesystem_registry


class PlanningService(RoutedService):
    """Coordinate context building and planning for a task."""

    def __init__(self, router: Router, factory: ProviderFactory) -> None:
        super().__init__(router, factory)

    async def plan(
        self,
        task: str,
        workspace: str,
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> PlanResult:
        """Build context for ``workspace`` and plan how to accomplish ``task``."""
        request = RoutingRequest(
            task=task,
            offline=offline,
            long_context=True,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        async with self._routed(request) as (decision, provider):
            engine = ContextEngine(filesystem_registry(workspace))
            context = await ContextBuilderAgent(engine).run(
                ContextRequest(query=task, max_tokens=decision.context_max_tokens)
            )
            plan = await PlannerAgent(provider, decision.model).run(
                PlannerInput(task=task, context_messages=context.messages)
            )
        return PlanResult(
            provider=decision.provider,
            model=decision.model,
            plan=plan,
            context_files=context.files_used,
        )
