"""Tests for memory backend selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora.core.errors import ConfigurationError
from aurora.memory import (
    FileMemory,
    InMemoryMemory,
    build_memory,
    build_memory_from_env,
)


def test_default_is_in_process() -> None:
    assert isinstance(build_memory(), InMemoryMemory)


def test_file_backend_uses_given_path(tmp_path: Path) -> None:
    memory = build_memory("file", str(tmp_path))
    assert isinstance(memory, FileMemory)


def test_unknown_kind_raises() -> None:
    with pytest.raises(ConfigurationError):
        build_memory("redis")


def test_from_env_selects_file_backend(tmp_path: Path) -> None:
    memory = build_memory_from_env(
        {"AURORA_MEMORY": "file", "AURORA_MEMORY_DIR": str(tmp_path)}
    )
    assert isinstance(memory, FileMemory)


def test_from_env_defaults_to_in_process() -> None:
    assert isinstance(build_memory_from_env({}), InMemoryMemory)
