"""Tests for the core layer."""

from __future__ import annotations

import pytest

from aurora.core import (
    ChatRequest,
    ConfigurationError,
    Message,
    Role,
    Settings,
    Usage,
)


def test_usage_total() -> None:
    assert Usage(prompt_tokens=3, completion_tokens=4).total_tokens == 7


def test_chat_request_requires_messages() -> None:
    with pytest.raises(ValueError):
        ChatRequest(model="m", messages=[])


def test_chat_request_temperature_bounds() -> None:
    with pytest.raises(ValueError):
        ChatRequest(
            model="m",
            messages=[Message(role=Role.USER, content="hi")],
            temperature=5.0,
        )


def test_settings_from_env_reads_keys_and_overrides() -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "sk-test",
            "AURORA_OLLAMA_BASE_URL": "http://elsewhere:1234",
        }
    )
    assert settings.require("openai").api_key == "sk-test"
    assert settings.require("ollama").base_url == "http://elsewhere:1234"
    assert settings.require("anthropic").api_key is None


def test_settings_require_unknown_raises() -> None:
    with pytest.raises(ConfigurationError):
        Settings().require("openai")
