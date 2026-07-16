"""Tests for the router layer."""

from __future__ import annotations

import pytest

from aurora.app.config.models import AppSettings, ProviderSettings
from aurora.app.core.exceptions import RouterError
from aurora.app.router import Capability, Router, RoutingRequest, build_catalog


def _settings(**keys: str) -> AppSettings:
    """Build settings; provider names in ``keys`` get an API key."""
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


# --- availability ---------------------------------------------------------


def test_local_model_always_available_cloud_requires_key() -> None:
    catalog = build_catalog(_settings(openai="sk-x"))
    available = {m.model for m in catalog.available()}
    assert "llama3.2" in available  # local, no key needed
    assert "gpt-4o" in available  # openai key provided
    assert "claude-sonnet-4" not in available  # no anthropic key


# --- selection ------------------------------------------------------------


def test_free_local_model_wins_on_cost_when_capable() -> None:
    # A plain chat/code task is satisfied by the free, local model.
    decision = _router(openai="sk-x").route(RoutingRequest(task="write a function"))
    assert (decision.provider, decision.model) == ("ollama", "llama3.2")
    assert decision.estimated_cost_per_1k == 0.0


def test_offline_forces_local_model() -> None:
    decision = _router(openai="sk-x").route(
        RoutingRequest(task="explain code", offline=True)
    )
    assert decision.provider == "ollama"
    assert "offline" not in decision.reason or decision.model == "llama3.2"


def test_required_capability_filters_pool() -> None:
    decision = _router(openai="sk-x", gemini="g").route(
        RoutingRequest(
            task="describe this image",
            required_capabilities=frozenset({Capability.VISION}),
        )
    )
    # Only gpt-4o and gemini have VISION (llama lacks it); gemini is cheaper.
    assert decision.model == "gemini-1.5-pro"


def test_needs_tools_adds_capability_and_tools() -> None:
    decision = _router(openai="sk-x").route(
        RoutingRequest(task="refactor and run tests", needs_tools=True)
    )
    assert decision.tools == ["filesystem", "terminal", "git"]
    assert Capability.TOOLS  # sanity


def test_long_context_sets_budget_and_capability() -> None:
    decision = _router(anthropic="sk-a").route(
        RoutingRequest(task="summarize repo", long_context=True)
    )
    assert decision.model == "claude-sonnet-4"
    assert decision.context_max_tokens == 8000


def test_explicit_model_preference_wins() -> None:
    decision = _router(openai="sk-x").route(
        RoutingRequest(task="anything", prefer_model="gpt-4o")
    )
    assert decision.model == "gpt-4o"
    assert decision.reason == "explicit model preference"


def test_preferred_provider_is_favored() -> None:
    decision = _router(openai="sk-x", gemini="g").route(
        RoutingRequest(task="reason about design", prefer_provider="gemini")
    )
    assert decision.provider == "gemini"


def test_max_cost_filters_expensive_models() -> None:
    # needs_tools excludes the free local model (no TOOLS); the cost cap then
    # rules out gpt-4o (5.0), leaving the affordable gpt-4o-mini (0.15).
    decision = _router(openai="sk-x", anthropic="sk-a").route(
        RoutingRequest(task="cheap task", needs_tools=True, max_cost_per_1k=1.0)
    )
    assert decision.estimated_cost_per_1k <= 1.0
    assert decision.model == "gpt-4o-mini"


def test_no_candidate_raises_router_error() -> None:
    # Offline with no local model satisfying VISION -> nothing available.
    with pytest.raises(RouterError):
        _router(openai="sk-x").route(
            RoutingRequest(
                task="see image",
                offline=True,
                required_capabilities=frozenset({Capability.VISION}),
            )
        )


def test_no_configured_cloud_keys_still_routes_to_local() -> None:
    decision = _router().route(RoutingRequest(task="hello"))
    assert decision.provider == "ollama"
