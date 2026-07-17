"""Tests for the tools layer: framework and filesystem tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora.app.core.exceptions import ConfigurationError, RegistryError
from aurora.app.tools import Permission
from aurora.app.tools.filesystem import filesystem_registry
from aurora.app.tools.filesystem.tools import ReadFileTool, WriteFileTool

# --- framework ------------------------------------------------------------


def test_spec_exposes_schemas_and_permissions(tmp_path: Path) -> None:
    spec = WriteFileTool(str(tmp_path)).spec()
    assert spec["name"] == "write_file"
    assert spec["category"] == "filesystem"
    assert "write" in spec["permissions"]
    assert spec["input_schema"]["type"] == "object"
    assert "content" in spec["output_schema"]["properties"] or spec["output_schema"]


async def test_invalid_arguments_return_structured_error(tmp_path: Path) -> None:
    result = await filesystem_registry(str(tmp_path)).invoke("read_file", {})
    assert result.ok is False
    assert result.error is not None
    assert result.error["code"] == "validation_error"


async def test_permission_enforcement(tmp_path: Path) -> None:
    registry = filesystem_registry(str(tmp_path))
    args = {"path": "a.txt", "content": "hi"}
    denied = await registry.invoke(
        "write_file", args, granted=frozenset({Permission.READ})
    )
    assert denied.ok is False
    assert denied.error["code"] == "permission_denied"
    assert "write" in denied.error["details"]["missing"]

    allowed = await registry.invoke(
        "write_file", args, granted=frozenset({Permission.WRITE})
    )
    assert allowed.ok is True


async def test_none_grant_allows_all(tmp_path: Path) -> None:
    result = await filesystem_registry(str(tmp_path)).invoke(
        "write_file", {"path": "a.txt", "content": "hi"}
    )
    assert result.ok is True


def test_duplicate_and_unknown(tmp_path: Path) -> None:
    registry = filesystem_registry(str(tmp_path))
    with pytest.raises(ConfigurationError):
        registry.register(ReadFileTool(str(tmp_path)))
    with pytest.raises(RegistryError):
        registry.get("ghost")


# --- filesystem behaviour -------------------------------------------------


async def test_write_read_roundtrip(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    write = await reg.invoke("write_file", {"path": "d/a.txt", "content": "hello"})
    assert write.ok and write.data["bytes_written"] == 5
    read = await reg.invoke("read_file", {"path": "d/a.txt"})
    assert read.data["content"] == "hello"
    assert read.data["size_bytes"] == 5


async def test_overwrite_creates_backup(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    await reg.invoke("write_file", {"path": "a.txt", "content": "v1"})
    second = await reg.invoke("write_file", {"path": "a.txt", "content": "v2"})
    assert second.data["backup"] == "a.txt.bak"
    assert (tmp_path / "a.txt.bak").read_text() == "v1"
    assert (tmp_path / "a.txt").read_text() == "v2"


async def test_overwrite_disabled_fails(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    await reg.invoke("write_file", {"path": "a.txt", "content": "v1"})
    result = await reg.invoke(
        "write_file", {"path": "a.txt", "content": "v2", "overwrite": False}
    )
    assert result.ok is False and result.error["code"] == "tool_error"


async def test_atomic_write_leaves_no_temp_files(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    await reg.invoke("write_file", {"path": "a.txt", "content": "x"})
    assert [p.name for p in tmp_path.iterdir()] == ["a.txt"]


async def test_delete(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    await reg.invoke("write_file", {"path": "a.txt", "content": "x"})
    result = await reg.invoke("delete_file", {"path": "a.txt"})
    assert result.data["deleted"] is True
    assert not (tmp_path / "a.txt").exists()
    missing = await reg.invoke("delete_file", {"path": "a.txt"})
    assert missing.ok is False


async def test_rename(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    await reg.invoke("write_file", {"path": "a.txt", "content": "x"})
    result = await reg.invoke("rename_file", {"src": "a.txt", "dst": "b/c.txt"})
    assert result.ok and result.data["dst"] == "b/c.txt"
    assert (tmp_path / "b" / "c.txt").exists()


async def test_rename_to_existing_fails(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    await reg.invoke("write_file", {"path": "a.txt", "content": "x"})
    await reg.invoke("write_file", {"path": "b.txt", "content": "y"})
    result = await reg.invoke("rename_file", {"src": "a.txt", "dst": "b.txt"})
    assert result.ok is False


async def test_search(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    await reg.invoke("write_file", {"path": "a.txt", "content": "alpha\nneedle here\n"})
    await reg.invoke("write_file", {"path": "b.txt", "content": "no match"})
    result = await reg.invoke("search_project", {"query": "needle"})
    assert result.data["count"] == 1
    hit = result.data["matches"][0]
    assert hit["path"] == "a.txt" and hit["line"] == 2


async def test_search_ignores_vcs_and_secret_files(tmp_path: Path) -> None:
    # .git internals and .env must never appear in results (noise + secrets).
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    (tmp_path / ".git" / "hooks" / "pre-push.sample").write_text("needle\n")
    (tmp_path / ".env").write_text("API_KEY=needle\n")
    (tmp_path / ".env.example").write_text("API_KEY=needle\n")
    (tmp_path / "keep.txt").write_text("needle\n")
    reg = filesystem_registry(str(tmp_path))
    result = await reg.invoke("search_project", {"query": "needle"})
    paths = {m["path"] for m in result.data["matches"]}
    assert paths == {"keep.txt", ".env.example"}


async def test_search_truncates(tmp_path: Path) -> None:
    reg = filesystem_registry(str(tmp_path))
    await reg.invoke("write_file", {"path": "a.txt", "content": "x\nx\nx\n"})
    result = await reg.invoke("search_project", {"query": "x", "max_results": 2})
    assert result.data["truncated"] is True
    assert result.data["count"] == 2


@pytest.mark.parametrize("bad", ["../escape.txt", "/etc/passwd"])
async def test_path_traversal_rejected(tmp_path: Path, bad: str) -> None:
    result = await filesystem_registry(str(tmp_path)).invoke("read_file", {"path": bad})
    assert result.ok is False
    assert result.error["code"] == "validation_error"
