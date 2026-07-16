"""Tests for the provider registry."""

from __future__ import annotations

import pytest

from aurora.core import ConfigurationError, ProviderConfig
from aurora.providers import build_provider, registered_providers
from aurora.providers.anthropic import AnthropicProvider
from aurora.providers.gemini import GeminiProvider
from aurora.providers.ollama import OllamaProvider
from aurora.providers.openai import OpenAIProvider
from aurora.providers.xai import XAIProvider


def test_all_architecture_providers_registered() -> None:
    assert registered_providers() == (
        "anthropic",
        "gemini",
        "ollama",
        "openai",
        "xai",
    )


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        ("ollama", OllamaProvider),
        ("openai", OpenAIProvider),
        ("anthropic", AnthropicProvider),
        ("xai", XAIProvider),
        ("gemini", GeminiProvider),
    ],
)
def test_build_provider_returns_expected_class(name: str, cls: type) -> None:
    provider = build_provider(name, ProviderConfig(base_url="http://x"))
    assert isinstance(provider, cls)
    assert provider.name == name


def test_build_unknown_provider_raises() -> None:
    with pytest.raises(ConfigurationError):
        build_provider("nope", ProviderConfig(base_url="http://x"))
