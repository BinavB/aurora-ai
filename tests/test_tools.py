"""Tests for the tools layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora.core import ConfigurationError
from aurora.tools import ToolRegistry, default_registry


async def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    registry = default_registry(str(tmp_path))
    write = await registry.invoke("write_file", path="notes/a.txt", content="hello")
    assert write.ok
    read = await registry.invoke("read_file", path="notes/a.txt")
    assert read.ok and read.output == "hello"


async def test_list_dir(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    registry = default_registry(str(tmp_path))
    result = await registry.invoke("list_dir", path=".")
    assert result.ok
    assert result.output.splitlines() == ["f.txt", "sub/"]


async def test_sandbox_escape_is_rejected(tmp_path: Path) -> None:
    registry = default_registry(str(tmp_path))
    result = await registry.invoke("read_file", path="../secret.txt")
    assert not result.ok
    assert "escape" in result.output.lower()


async def test_read_missing_file_fails_gracefully(tmp_path: Path) -> None:
    registry = default_registry(str(tmp_path))
    result = await registry.invoke("read_file", path="nope.txt")
    assert not result.ok


def test_specs_expose_schema(tmp_path: Path) -> None:
    specs = {s["name"] for s in default_registry(str(tmp_path)).specs()}
    assert specs == {"read_file", "write_file", "list_dir"}


def test_duplicate_registration_rejected(tmp_path: Path) -> None:
    registry = default_registry(str(tmp_path))
    from aurora.tools.fs import ReadFileTool

    with pytest.raises(ConfigurationError):
        registry.register(ReadFileTool(str(tmp_path)))


async def test_unknown_tool_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        await ToolRegistry().invoke("ghost")
