"""Tests for the services layer (agents driven by fakes, no network)."""

from __future__ import annotations

from pathlib import Path

from aurora.app.config.models import AppSettings, ProviderSettings
from aurora.app.core.exceptions import ProviderRequestError
from aurora.app.core.types import ChatRequest, ChatResponse
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


class _AlwaysFail(BaseProvider):
    """A provider whose chat always fails, to exercise failover."""

    name = "failing"

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        raise ProviderRequestError("simulated outage")


class SelectiveFactory(ProviderFactory):
    """Fails for named providers, returns a working provider otherwise."""

    def __init__(self, failing: set[str], ok: BaseProvider) -> None:
        self._failing = failing
        self._ok = ok
        self.created: list[str] = []

    def create(self, provider: str) -> BaseProvider:
        self.created.append(provider)
        if provider in self._failing:
            return _AlwaysFail(ProviderSettings(base_url="http://x"))
        return self._ok


def _settings(**keys: str) -> AppSettings:
    providers = {
        "ollama": ProviderSettings(base_url="http://localhost:11434"),
        "openai": ProviderSettings(base_url="https://api.openai.com/v1"),
        "anthropic": ProviderSettings(base_url="https://api.anthropic.com/v1"),
        "gemini": ProviderSettings(base_url="https://gen.googleapis.com"),
        "xai": ProviderSettings(base_url="https://api.x.ai/v1"),
        "groq": ProviderSettings(base_url="https://api.groq.com/openai/v1"),
        "cerebras": ProviderSettings(base_url="https://api.cerebras.ai/v1"),
        "mistral": ProviderSettings(base_url="https://api.mistral.ai/v1"),
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


class _Streamer(BaseProvider):
    """A provider that streams fixed deltas and records when it is closed."""

    name = "streamer"

    def __init__(self, chunks: list[str]) -> None:
        super().__init__(ProviderSettings(base_url="http://s"))
        self._chunks = chunks
        self.closed = False

    async def _stream(self, request: ChatRequest):
        for chunk in self._chunks:
            yield chunk

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


async def test_stream_chat_yields_tokens_persists_and_closes() -> None:
    provider = _Streamer(["Hel", "lo"])
    store = MemoryStore(Database())
    await store.open()
    service = ChatService(_router(), FakeFactory(provider), store)

    chunks = [chunk async for chunk in service.stream_chat("s", "hi")]
    tokens = [c.content for c in chunks if c.type == "token"]
    done = next(c for c in chunks if c.type == "done")

    assert tokens == ["Hel", "lo"]
    assert done.content == "Hello"
    assert done.provider == "ollama"
    assert provider.closed is True
    # The full turn (user + assembled assistant reply) is persisted.
    history = await store.conversation("s")
    assert [m.content for m in history] == ["hi", "Hello"]


async def test_stream_chat_fails_over_before_first_token() -> None:
    # The CHAT chain leads with Gemini; it fails to open -> fall over to local.
    good = _Streamer(["ok"])
    factory = SelectiveFactory(failing={"gemini"}, ok=good)
    store = MemoryStore(Database())
    await store.open()
    service = ChatService(_router(gemini="g"), factory, store)

    chunks = [chunk async for chunk in service.stream_chat("s", "hi")]
    done = next(c for c in chunks if c.type == "done")
    assert factory.created[0] == "gemini"  # tried the primary first
    assert done.provider == "ollama"  # then failed over to the local model
    assert done.content == "ok"


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


async def test_review_summary_tolerates_markdown_heading() -> None:
    # Models often emit '**Summary:**' or '## Summary' rather than 'Summary:'.
    factory = FakeFactory(ScriptedProvider("- bug A\n- bug B\n\n**Summary:** two bugs"))
    outcome = await ReviewService(_router(), factory).review("code")
    assert outcome.result.summary == "two bugs"


async def test_review_summary_falls_back_when_unlabeled() -> None:
    # No 'Summary:' line -> a useful count instead of 'No summary provided.'
    factory = FakeFactory(ScriptedProvider("- missing tests\n- no types"))
    outcome = await ReviewService(_router(), factory).review("code")
    assert outcome.result.summary == "2 issues identified."


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
    # llama3.2 is tool-capable and free, so the local model handles it.
    assert result.provider == "ollama"


async def test_failover_skips_failing_provider() -> None:
    # Review chain leads with Groq; Groq fails -> falls over to Gemini.
    good = ScriptedProvider("- looks fine\nSummary: ok")
    factory = SelectiveFactory(failing={"groq"}, ok=good)
    service = ReviewService(_router(gemini="g", groq="gk"), factory)
    outcome = await service.review("def f():\n    return 1")
    assert factory.created[0] == "groq"  # tried the primary (Groq) first
    assert outcome.provider == "gemini"  # then failed over to the next candidate


async def test_chat_with_images_routes_to_vision_model() -> None:
    factory = FakeFactory(ScriptedProvider("I can see a cat."))
    store = MemoryStore(Database())
    await store.open()
    service = ChatService(_router(gemini="g", groq="gk"), factory, store)
    reply = await service.chat(
        "s", "what is this?", images=["data:image/png;base64,QQ=="]
    )
    # only gemini has VISION -> routed there
    assert reply.provider == "gemini"
    assert reply.content == "I can see a cat."


async def test_offline_chat_prefers_local(tmp_path: Path) -> None:
    factory = FakeFactory(RecordingEcho())
    store = MemoryStore(Database())
    await store.open()
    service = ChatService(_router(openai="sk-x"), factory, store)
    reply = await service.chat("s", "hi", offline=True)
    assert reply.provider == "ollama"
