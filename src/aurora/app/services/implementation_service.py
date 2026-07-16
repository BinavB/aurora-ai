"""Implementation service: generate code and, on approval, apply it.

Generation (coder) and application (executor via tools) are distinct steps.
Without approval the service performs a dry run — it returns the proposed
contents but writes nothing.
"""

from __future__ import annotations

from aurora.app.agents.coder import CoderAgent
from aurora.app.agents.context_builder import ContextBuilderAgent
from aurora.app.agents.executor import ExecutorAgent
from aurora.app.agents.models import CoderInput, ExecutorInput, WriteFileAction
from aurora.app.context.engine import ContextEngine
from aurora.app.context.models import ContextRequest
from aurora.app.router.models import RoutingRequest
from aurora.app.router.router import Router
from aurora.app.services.base import RoutedService
from aurora.app.services.factory import ProviderFactory
from aurora.app.services.models import ImplementResult
from aurora.app.tools.filesystem import filesystem_registry
from aurora.app.tools.terminal import terminal_registry


class ImplementationService(RoutedService):
    """Coordinate context, code generation, and (approved) execution."""

    def __init__(self, router: Router, factory: ProviderFactory) -> None:
        super().__init__(router, factory)

    async def implement(
        self,
        instruction: str,
        target_path: str,
        workspace: str,
        approve: bool = False,
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> ImplementResult:
        """Generate contents for ``target_path``; write them only if approved."""
        request = RoutingRequest(
            task=instruction,
            offline=offline,
            needs_tools=True,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        async with self._routed(request) as (decision, provider):
            engine = ContextEngine(filesystem_registry(workspace))
            context = await ContextBuilderAgent(engine).run(
                ContextRequest(query=instruction, max_tokens=decision.context_max_tokens)
            )
            proposed = await CoderAgent(provider, decision.model).run(
                CoderInput(
                    instruction=instruction,
                    target_path=target_path,
                    context_messages=context.messages,
                )
            )
        report = None
        if approve:
            executor = ExecutorAgent(
                filesystem_registry(workspace), terminal_registry(workspace)
            )
            report = await executor.run(
                ExecutorInput(
                    actions=[
                        WriteFileAction(path=proposed.path, content=proposed.content)
                    ]
                )
            )
        return ImplementResult(
            provider=decision.provider,
            model=decision.model,
            proposed=proposed,
            executed=approve,
            report=report,
        )
