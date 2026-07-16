"""Tests for the config layer."""

from __future__ import annotations

import pytest

from aurora.app.config import AppSettings, load_settings
from aurora.app.core.exceptions import ConfigurationError


def test_load_settings_reads_keys_and_overrides() -> None:
    settings = load_settings(
        {
            "OPENAI_API_KEY": "sk-test",
            "AURORA_OLLAMA_BASE_URL": "http://elsewhere:1234",
            "AURORA_LOG_LEVEL": "DEBUG",
        }
    )
    assert settings.log_level == "DEBUG"
    assert settings.provider("openai").api_key == "sk-test"
    assert settings.provider("ollama").base_url == "http://elsewhere:1234"
    assert settings.provider("anthropic").api_key is None


def test_all_architecture_providers_configured() -> None:
    settings = load_settings({})
    for name in ("ollama", "openai", "anthropic", "xai", "gemini"):
        assert settings.provider(name).base_url


def test_unknown_provider_raises() -> None:
    with pytest.raises(ConfigurationError):
        AppSettings().provider("openai")
