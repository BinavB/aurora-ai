"""Tests for the chain-based router."""

from __future__ import annotations

import pytest

from aurora.app.config.models import AppSettings, ProviderSettings
from aurora.app.core.exceptions import RouterError
from aurora.app.router import (
    Capability,
    Router,
    RoutingRequest,
    TaskKind,
    build_catalog,
)

_BASE = {
    "ollama": "http://localhost:11434",
    "gemini": "https://gen.googleapis.com",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
}


def _settings(**keys: str) -> AppSettings:
    providers = {n: ProviderSettings(base_url=u) for n, u in _BASE.items()}
    for name, key in keys.items():
        providers[name] = providers[name].model_copy(update={"api_key": key})
    return AppSettings(providers=providers)


def _router(**keys: str) -> Router:
    return Router(build_catalog(_settings(**keys)))


# --- availability ---------------------------------------------------------


def test_local_always_available_cloud_requires_key() -> None:
    catalog = build_catalog(_settings(gemini="g"))
    avail = {(m.provider, m.model) for m in catalog.available()}
    assert ("ollama", "llama3.2") in avail  # local, no key
    assert ("gemini", "gemini-flash-latest") in avail  # key provided
    assert ("groq", "llama-3.3-70b-versatile") not in avail  # no groq key


# --- chains ---------------------------------------------------------------


def test_chat_primary_is_gemini_flash() -> None:
    d = _router(gemini="g", groq="gk").route(
        RoutingRequest(task="hi", kind=TaskKind.CHAT)
    )
    assert (d.provider, d.model) == ("gemini", "gemini-flash-latest")


def test_chat_falls_back_to_groq_without_gemini() -> None:
    d = _router(groq="gk").route(RoutingRequest(task="hi", kind=TaskKind.CHAT))
    assert (d.provider, d.model) == ("groq", "llama-3.3-70b-versatile")


def test_plan_primary_is_groq_reasoning_then_gemini() -> None:
    d1 = _router(groq="gk").route(RoutingRequest(task="x", kind=TaskKind.PLAN))
    assert (d1.provider, d1.model) == ("groq", "openai/gpt-oss-120b")
    # No groq key -> falls through to gemini flash.
    d2 = _router(gemini="g").route(RoutingRequest(task="x", kind=TaskKind.PLAN))
    assert (d2.provider, d2.model) == ("gemini", "gemini-flash-latest")


def test_review_primary_is_groq_reasoning() -> None:
    d = _router(groq="gk").route(RoutingRequest(task="x", kind=TaskKind.REVIEW))
    assert (d.provider, d.model) == ("groq", "openai/gpt-oss-120b")


def test_implement_primary_is_codestral_then_groq() -> None:
    d1 = _router(mistral="mk").route(RoutingRequest(task="x", kind=TaskKind.IMPLEMENT))
    assert (d1.provider, d1.model) == ("mistral", "codestral-latest")
    d2 = _router(groq="gk").route(RoutingRequest(task="x", kind=TaskKind.IMPLEMENT))
    assert (d2.provider, d2.model) == ("groq", "llama-3.3-70b-versatile")


def test_summarize_and_explain_chains() -> None:
    s = _router(gemini="g").route(RoutingRequest(task="x", kind=TaskKind.SUMMARIZE))
    assert s.model == "gemini-flash-latest"  # summarize leads with gemini flash
    # explain leads with groq reasoning; without groq it falls to gemini flash
    e = _router(groq="gk").route(RoutingRequest(task="x", kind=TaskKind.EXPLAIN))
    assert e.model == "openai/gpt-oss-120b"
    e2 = _router(gemini="g").route(RoutingRequest(task="x", kind=TaskKind.EXPLAIN))
    assert e2.model == "gemini-flash-latest"


def test_offline_uses_local_chain_link() -> None:
    d = _router(gemini="g").route(
        RoutingRequest(task="x", kind=TaskKind.CHAT, offline=True)
    )
    assert d.provider == "ollama"


def test_no_keys_routes_local() -> None:
    d = _router().route(RoutingRequest(task="x", kind=TaskKind.CHAT))
    assert d.provider == "ollama"


def test_rank_is_ordered_for_failover() -> None:
    ranked = _router(gemini="g", groq="gk").rank(
        RoutingRequest(task="x", kind=TaskKind.CHAT)
    )
    pairs = [(d.provider, d.model) for d in ranked]
    # gemini flash first, groq llama second (chain order), locals later
    assert pairs[0] == ("gemini", "gemini-flash-latest")
    assert ("groq", "llama-3.3-70b-versatile") in pairs
    assert ("ollama", "llama3.2") in pairs


def test_prefer_provider_moves_to_front() -> None:
    d = _router(gemini="g", groq="gk").route(
        RoutingRequest(task="x", kind=TaskKind.CHAT, prefer_provider="groq")
    )
    assert d.provider == "groq"


def test_prefer_model_wins() -> None:
    d = _router(groq="gk").route(
        RoutingRequest(task="x", kind=TaskKind.CHAT, prefer_model="qwen/qwen3-32b")
    )
    assert d.model == "qwen/qwen3-32b"


def test_vision_requirement_selects_gemini() -> None:
    d = _router(gemini="g", groq="gk").route(
        RoutingRequest(
            task="x",
            kind=TaskKind.CHAT,
            required_capabilities=frozenset({Capability.VISION}),
        )
    )
    assert d.provider == "gemini"


def test_no_candidate_raises_router_error() -> None:
    # Offline + vision: no local model has vision.
    with pytest.raises(RouterError):
        _router().route(
            RoutingRequest(
                task="x",
                kind=TaskKind.CHAT,
                offline=True,
                required_capabilities=frozenset({Capability.VISION}),
            )
        )
