"""Tests for the services layer (agents driven by fakes, no network)."""

from __future__ import annotations

from pathlib import Path

from aurora.app.config.models import AppSettings, ProviderSettings
from aurora.app.database import Database
from aurora.app.memory import MemoryStore
from aurora.app.providers.base import BaseProvider
from aurora.app.router import Router, build_catalog
from aurora.app.services import (
    ChatService,
    ImplementationService,
    PlanningService,
    ReviewService,
)
from aurora.app.services.factory import ProviderFactory
from tests.app.conftest import EchoProvider, ScriptedProvider


def _settings(**keys: str) -> AppSettings:
    providers = {
        "ollama": ProviderSettings(base_url="http://localhost:11434"),
        "openai": ProviderSettings(base_url="https://api.openai.com/v1"),
        "anthropic": ProviderSettings(base_url="https://api.anthropic.com/v1"),
        "gemini": ProviderSettings(base_url="https://gen.googleapis.com"),
        "xai": ProviderSettings(base_url="https://api.x.ai/v1"),
    }
    for name, key in keys.items():
        providers[name] = providers[name].model_copy(update={"api_key": key})
    return AppSettings(providers=providers)


def _router(**keys: str) -> Router:
    return Router(build_catalog(_settings(**keys)))


class FakeFactory(ProviderFactory):
    """Returns a fixed provider for any name and records what was created."""

    def __init__(self, provider: BaseProvider) -> None:
        self._provider = provider
        self.created: list[str] = []

    def create(self, provider: str) -> BaseProvider:
        self.created.append(provider)
        return self._provider


class RecordingEcho(EchoProvider):
    """Echo provider that records whether it was closed."""

    def __init__(self) -> None:
        from aurora.app.config.models import ProviderSettings as PS

        super().__init__(PS(base_url="http://echo.local"))
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        await super().aclose()


# --- chat -----------------------------------------------------------------


async def test_chat_service_routes_persists_and_closes_provider() -> None:
    provider = RecordingEcho()
    factory = FakeFactory(provider)
    store = MemoryStore(Database())
    await store.open()
    service = ChatService(_router(), factory, store)

    reply = await service.chat("s", "hello")
    assert reply.provider == "ollama"  # free local model wins for plain chat
    assert reply.content == "echo[1]: hello"
    assert len(await store.conversation("s")) == 2
    assert provider.closed is True  # provider lifecycle handled by the service
    assert factory.created == ["ollama"]


# --- planning -------------------------------------------------------------


async def test_planning_service_builds_context_and_plan(tmp_path: Path) -> None:
    (tmp_path / "cache.py").write_text("def cache_get(k):\n    return k\n", "utf-8")
    factory = FakeFactory(ScriptedProvider("1. Read cache\n2. Add TTL"))
    service = PlanningService(_router(openai="sk-x"), factory)

    result = await service.plan("improve the cache module", str(tmp_path))
    assert [s.description for s in result.plan.steps] == ["Read cache", "Add TTL"]
    assert "cache.py" in result.context_files


# --- review ---------------------------------------------------------------


async def test_review_service_returns_findings() -> None:
    factory = FakeFactory(ScriptedProvider("- no docstring\nSummary: minor"))
    service = ReviewService(_router(), factory)
    outcome = await service.review("def f():\n    return 1")
    assert outcome.result.findings == ["no docstring"]
    assert outcome.result.summary == "minor"


# --- implementation -------------------------------------------------------


async def test_implement_dry_run_writes_nothing(tmp_path: Path) -> None:
    factory = FakeFactory(ScriptedProvider("print('generated')"))
    service = ImplementationService(_router(openai="sk-x"), factory)
    result = await service.implement("create a script", "out.py", str(tmp_path))
    assert result.executed is False
    assert result.report is None
    assert result.proposed.content == "print('generated')"
    assert not (tmp_path / "out.py").exists()


async def test_implement_with_approval_writes_file(tmp_path: Path) -> None:
    factory = FakeFactory(ScriptedProvider("print('generated')"))
    service = ImplementationService(_router(openai="sk-x"), factory)
    result = await service.implement(
        "create a script", "out.py", str(tmp_path), approve=True
    )
    assert result.executed is True
    assert result.report is not None and result.report.ok is True
    assert (tmp_path / "out.py").read_text() == "print('generated')"


async def test_implement_needs_tools_selects_tool_capable_model(tmp_path: Path) -> None:
    factory = FakeFactory(ScriptedProvider("x = 1"))
    service = ImplementationService(_router(openai="sk-x"), factory)
    result = await service.implement("do it", "a.py", str(tmp_path))
    # Local llama lacks TOOLS; a tool-capable model is selected instead.
    assert result.provider == "openai"


async def test_offline_chat_prefers_local(tmp_path: Path) -> None:
    factory = FakeFactory(RecordingEcho())
    store = MemoryStore(Database())
    await store.open()
    service = ChatService(_router(openai="sk-x"), factory, store)
    reply = await service.chat("s", "hi", offline=True)
    assert reply.provider == "ollama"
