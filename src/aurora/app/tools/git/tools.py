"""Concrete git tools.

Git operations happen only through these tools, which run ``git`` via the
sandboxed :class:`TerminalRunner`. Commits require explicit approval; there is
no push tool — nothing is ever pushed automatically.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from aurora.app.core.exceptions import ConfirmationRequiredError, ToolError
from aurora.app.tools.base import BaseTool
from aurora.app.tools.git.models import (
    GitAddInput,
    GitAddOutput,
    GitCommitInput,
    GitCommitOutput,
    GitDiffInput,
    GitDiffOutput,
    GitStatusOutput,
)
from aurora.app.tools.git.parser import parse_status
from aurora.app.tools.models import Permission, ToolMetadata
from aurora.app.tools.terminal.models import CommandResult
from aurora.app.tools.terminal.runner import TerminalRunner

_CATEGORY = "git"


class _GitTool(BaseTool):
    """Base for git tools sharing a runner rooted at the repository."""

    def __init__(self, repo_dir: str | Path) -> None:
        self._runner = TerminalRunner(repo_dir)
        super().__init__()

    async def _git(self, args: list[str]) -> CommandResult:
        """Run ``git`` with ``args``, raising :class:`ToolError` on failure."""
        result = await self._runner.run(["git", *args])
        if result.exit_code != 0:
            raise ToolError(
                f"git {args[0]} failed",
                details={"stderr": result.stderr.strip(), "exit_code": result.exit_code},
            )
        return result


class GitStatusInput(BaseModel):
    """No input required for status."""


class GitStatusTool(_GitTool):
    """Report the working-tree status."""

    metadata = ToolMetadata(
        name="git_status",
        description="Report the git working-tree status as structured entries.",
        category=_CATEGORY,
        permissions=frozenset({Permission.GIT}),
    )
    input_model = GitStatusInput
    output_model = GitStatusOutput

    async def execute(self, payload: GitStatusInput) -> GitStatusOutput:
        result = await self._git(["status", "--porcelain"])
        entries = parse_status(result.stdout)
        return GitStatusOutput(entries=entries, clean=not entries)


class GitDiffTool(_GitTool):
    """Show a unified diff of unstaged or staged changes."""

    metadata = ToolMetadata(
        name="git_diff",
        description="Show a unified diff of working-tree or staged changes.",
        category=_CATEGORY,
        permissions=frozenset({Permission.GIT}),
    )
    input_model = GitDiffInput
    output_model = GitDiffOutput

    async def execute(self, payload: GitDiffInput) -> GitDiffOutput:
        args = ["diff"]
        if payload.staged:
            args.append("--staged")
        if payload.path:
            args.extend(["--", payload.path])
        result = await self._git(args)
        return GitDiffOutput(diff=result.stdout, has_changes=bool(result.stdout.strip()))


class GitAddTool(_GitTool):
    """Stage paths for the next commit."""

    metadata = ToolMetadata(
        name="git_add",
        description="Stage one or more paths for commit.",
        category=_CATEGORY,
        permissions=frozenset({Permission.GIT}),
    )
    input_model = GitAddInput
    output_model = GitAddOutput

    async def execute(self, payload: GitAddInput) -> GitAddOutput:
        await self._git(["add", "--", *payload.paths])
        return GitAddOutput(staged=payload.paths)


class GitCommitTool(_GitTool):
    """Commit staged changes. Requires explicit approval."""

    metadata = ToolMetadata(
        name="git_commit",
        description="Commit staged changes (requires explicit approval).",
        category=_CATEGORY,
        permissions=frozenset({Permission.GIT}),
    )
    input_model = GitCommitInput
    output_model = GitCommitOutput

    async def execute(self, payload: GitCommitInput) -> GitCommitOutput:
        if not payload.approve:
            raise ConfirmationRequiredError(
                "Commit requires explicit approval (approve=true)",
                details={"message": payload.message},
            )
        await self._git(["commit", "-m", payload.message])
        ref = await self._git(["rev-parse", "--short", "HEAD"])
        return GitCommitOutput(committed=True, ref=ref.stdout.strip())
