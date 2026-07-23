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
from aurora.app.router.models import RoutingRequest, TaskKind
from aurora.app.services.base import RoutedService
from aurora.app.services.models import ImplementResult
from aurora.app.tools.filesystem import filesystem_registry
from aurora.app.tools.terminal import terminal_registry


class ImplementationService(RoutedService):
    """Coordinate context, code generation, and (approved) execution."""

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
            kind=TaskKind.IMPLEMENT,
            offline=offline,
            needs_tools=True,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        engine = ContextEngine(filesystem_registry(workspace))

        async def work(decision, provider):
            context = await ContextBuilderAgent(engine).run(
                ContextRequest(query=instruction, max_tokens=decision.context_max_tokens)
            )
            return await CoderAgent(provider, decision.model, self._system_prompt).run(
                CoderInput(
                    instruction=instruction,
                    target_path=target_path,
                    context_messages=context.messages,
                )
            )

        decision, proposed = await self._attempt(request, work)
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
