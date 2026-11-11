"""Tests for structured multi-agent collaboration."""

from __future__ import annotations

import asyncio

from aurora.app.config.models import AppSettings, ProviderSettings
from aurora.app.core.types import ChatRequest, ChatResponse
from aurora.app.providers.base import BaseProvider
from aurora.app.router import Router, build_catalog
from aurora.app.router.models import TaskKind
from aurora.app.services.collaboration_service import CollaborationService, Effort
from aurora.app.services.factory import ProviderFactory


class _RoleProvider(BaseProvider):
    """Echoes the system prompt's first word so we can see which role ran."""

    name = "role"

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        # brief marker of the last system framing + whether it's a synthesis
        system = next(
            (m.content for m in request.messages if m.role.value == "system"), ""
        )
        marker = system.split()[0] if system else "?"
        await asyncio.sleep(0)  # allow true concurrency
        return ChatResponse(model=request.model, content=f"{marker}-out")


class _Factory(ProviderFactory):
    def __init__(self) -> None:
        self.created: list[str] = []

    def create(self, provider: str) -> BaseProvider:
        self.created.append(provider)
        return _RoleProvider(ProviderSettings(base_url="http://x"))


def _service() -> CollaborationService:
    providers = {
        n: ProviderSettings(base_url="http://x", api_key="k")
        for n in ("gemini", "groq", "mistral", "ollama")
    }
    settings = AppSettings(providers=providers)
    return CollaborationService(Router(build_catalog(settings)), _Factory())


async def test_fast_effort_uses_single_agent() -> None:
    result = await _service().collaborate(TaskKind.CHAT, "hi", effort=Effort.FAST)
    assert len(result.roster) == 1
    assert result.roster[0].startswith("Solo")


async def test_balanced_effort_dispatches_two_specialists_plus_synth() -> None:
    result = await _service().collaborate(
        TaskKind.PLAN, "design a cache", effort=Effort.BALANCED
    )
    # dispatcher + 2 specialists + synthesizer
    assert len(result.roster) == 4
    assert result.roster[0].startswith("Dispatcher")
    assert result.roster[-1].startswith("Synthesizer")


async def test_max_effort_uses_more_specialists() -> None:
    result = await _service().collaborate(
        TaskKind.REVIEW, "def f(): pass", effort=Effort.MAX
    )
    # dispatcher + 3 specialists + synthesizer
    assert len(result.roster) == 5
    assert result.roster[0].startswith("Dispatcher")


async def test_small_question_in_max_gets_a_brief_solo_answer() -> None:
    result = await _service().collaborate(TaskKind.CHAT, "hi there", effort=Effort.MAX)
    assert len(result.roster) == 1
    assert result.effort_used == "fast"
    assert result.recommended_effort == "fast"


async def test_big_question_in_balanced_recommends_max() -> None:
    result = await _service().collaborate(
        TaskKind.CHAT,
        "design the architecture for a chat app and compare the trade-offs",
        effort=Effort.BALANCED,
    )
    assert result.effort_used == "balanced"
    assert result.recommended_effort == "max"


def test_recommend_effort_levels() -> None:
    from aurora.app.services.collaboration_service import recommend_effort

    assert recommend_effort("who built you") is Effort.FAST
    assert recommend_effort("[Style: calm]\n\nhello") is Effort.FAST
    assert recommend_effort("explain how a hash map works") is Effort.BALANCED
    assert recommend_effort("give me a detailed roadmap") is Effort.MAX
    assert recommend_effort("```py\nx = 1\n```") is Effort.MAX
