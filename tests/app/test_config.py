"""Tests for the config layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora.app.config import AppSettings, load_settings
from aurora.app.config.loader import read_dotenv
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


def test_read_dotenv_parses_and_strips(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# a comment\nGEMINI_API_KEY="gk-123"\nGROQ_API_KEY=abc\n\nBAD LINE\n',
        encoding="utf-8",
    )
    parsed = read_dotenv(env_file)
    assert parsed == {"GEMINI_API_KEY": "gk-123", "GROQ_API_KEY": "abc"}


def test_read_dotenv_missing_file_is_empty(tmp_path: Path) -> None:
    assert read_dotenv(tmp_path / "nope.env") == {}


def test_load_settings_reads_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("MISTRAL_API_KEY=mk-from-file\n", encoding="utf-8")
    settings = load_settings(dotenv_path=env_file)
    assert settings.provider("mistral").api_key == "mk-from-file"
