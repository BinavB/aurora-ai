"""Autonomous agent service: run a bounded ReAct loop over the full toolset.

The agent is given the filesystem, terminal, and git tools for the workspace
and iterates until the task is done. Because it can write files and run
commands, exposing it is gated by the caller (see the API layer); this service
assumes it is only reachable in a trusted context.
"""

from __future__ import annotations

from aurora.app.agents.autonomous import AutonomousAgent
from aurora.app.agents.models import AutonomousInput
from aurora.app.router.models import RoutingRequest, TaskKind
from aurora.app.router.router import Router
from aurora.app.services.base import RoutedService
from aurora.app.services.factory import ProviderFactory
from aurora.app.services.models import AgentResult
from aurora.app.tools.filesystem import filesystem_registry
from aurora.app.tools.git import git_registry
from aurora.app.tools.registry import ToolRegistry
from aurora.app.tools.terminal import terminal_registry
from aurora.app.tools.web import web_registry


def combined_registry(workspace: str) -> ToolRegistry:
    """A single registry exposing filesystem, terminal, git, and web tools."""
    registry = ToolRegistry()
    sources = (
        filesystem_registry(workspace),
        terminal_registry(workspace),
        git_registry(workspace),
        web_registry(),
    )
    for source in sources:
        for name in source.names():
            registry.register(source.get(name))
    return registry


class AutonomousService(RoutedService):
    """Coordinate routing and the autonomous tool-using loop."""

    def __init__(self, router: Router, factory: ProviderFactory) -> None:
        super().__init__(router, factory)

    async def run(
        self,
        task: str,
        workspace: str,
        *,
        max_steps: int = 12,
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> AgentResult:
        """Run the autonomous agent against ``workspace`` until done or bounded."""
        request = RoutingRequest(
            task=task,
            kind=TaskKind.IMPLEMENT,
            offline=offline,
            needs_tools=True,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        tools = combined_registry(workspace)

        async def work(decision, provider):
            return await AutonomousAgent(provider, decision.model, tools).run(
                AutonomousInput(task=task, max_steps=max_steps)
            )

        decision, report = await self._attempt(request, work)
        return AgentResult(
            provider=decision.provider, model=decision.model, report=report
        )
