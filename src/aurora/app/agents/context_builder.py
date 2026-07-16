"""Context builder agent: build token-efficient context for a request."""

from __future__ import annotations

from aurora.app.agents.base import BaseAgent
from aurora.app.context.engine import ContextEngine
from aurora.app.context.models import BuiltContext, ContextRequest


class ContextBuilderAgent(BaseAgent[ContextRequest, BuiltContext]):
    """Wrap the context engine as a single-task agent."""

    name = "context_builder"

    def __init__(self, engine: ContextEngine) -> None:
        self._engine = engine

    async def run(self, request: ContextRequest) -> BuiltContext:
        return await self._engine.build(request)
