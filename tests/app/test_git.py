"""Tests for the git tools layer (uses a real temporary repository)."""

from __future__ import annotations

from pathlib import Path

from aurora.app.tools import Permission
from aurora.app.tools.git import git_registry, parse_status
from aurora.app.tools.terminal.runner import TerminalRunner


async def _make_repo(path: Path) -> None:
    """Initialize a git repo with a deterministic identity."""
    runner = TerminalRunner(str(path))
    await runner.run(["git", "init"])
    await runner.run(["git", "config", "user.email", "test@aurora.local"])
    await runner.run(["git", "config", "user.name", "Aurora Test"])
    await runner.run(["git", "config", "commit.gpgsign", "false"])


# --- parser (unit) --------------------------------------------------------


def test_parse_status_handles_rename_and_untracked() -> None:
    entries = parse_status("?? new.txt\n M edited.txt\nR  old.txt -> renamed.txt\n")
    assert [(e.code, e.path) for e in entries] == [
        ("??", "new.txt"),
        (" M", "edited.txt"),
        ("R ", "renamed.txt"),
    ]


# --- behaviour ------------------------------------------------------------


async def test_status_reports_untracked(tmp_path: Path) -> None:
    await _make_repo(tmp_path)
    (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
    result = await git_registry(str(tmp_path)).invoke("git_status", {})
    assert result.ok is True
    assert result.data["clean"] is False
    assert result.data["entries"][0]["path"] == "a.txt"


async def test_add_then_commit_flow(tmp_path: Path) -> None:
    await _make_repo(tmp_path)
    (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
    reg = git_registry(str(tmp_path))

    added = await reg.invoke("git_add", {"paths": ["a.txt"]})
    assert added.ok is True and added.data["staged"] == ["a.txt"]

    # Commit without approval is refused.
    refused = await reg.invoke("git_commit", {"message": "init"})
    assert refused.ok is False
    assert refused.error["code"] == "confirmation_required"

    # Nothing was committed.
    status = await reg.invoke("git_status", {})
    assert status.data["clean"] is False

    # Approved commit succeeds and leaves a clean tree.
    committed = await reg.invoke("git_commit", {"message": "init", "approve": True})
    assert committed.ok is True and committed.data["committed"] is True
    assert committed.data["ref"]
    assert (await reg.invoke("git_status", {})).data["clean"] is True


async def test_diff_shows_changes(tmp_path: Path) -> None:
    await _make_repo(tmp_path)
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    reg = git_registry(str(tmp_path))
    await reg.invoke("git_add", {"paths": ["a.txt"]})
    await reg.invoke("git_commit", {"message": "init", "approve": True})

    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")
    diff = await reg.invoke("git_diff", {})
    assert diff.data["has_changes"] is True
    assert "a.txt" in diff.data["diff"]


async def test_no_push_tool_exists(tmp_path: Path) -> None:
    # Honors "never auto push": there is no push capability at all.
    assert "git_push" not in git_registry(str(tmp_path)).names()


async def test_git_permission_enforced(tmp_path: Path) -> None:
    await _make_repo(tmp_path)
    denied = await git_registry(str(tmp_path)).invoke(
        "git_status", {}, granted=frozenset({Permission.READ})
    )
    assert denied.ok is False
    assert denied.error["code"] == "permission_denied"


async def test_git_failure_is_structured(tmp_path: Path) -> None:
    # Not a git repository -> structured tool_error, not a crash.
    result = await git_registry(str(tmp_path)).invoke("git_status", {})
    assert result.ok is False
    assert result.error["code"] == "tool_error"
