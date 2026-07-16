"""Git tools: the only sanctioned path to git.

Operations run ``git`` through the sandboxed terminal runner. Commits require
explicit approval and there is no push capability — nothing is ever committed
or pushed automatically.
"""

from aurora.app.tools.git.parser import parse_status
from aurora.app.tools.git.tools import (
    GitAddTool,
    GitCommitTool,
    GitDiffTool,
    GitStatusTool,
)
from aurora.app.tools.registry import ToolRegistry


def git_registry(repo_dir: str) -> ToolRegistry:
    """Build a registry of the git tools rooted at ``repo_dir``.

    Args:
        repo_dir: Path to the git repository.

    Returns:
        A registry with status, diff, add, and commit tools.
    """
    return ToolRegistry(
        [
            GitStatusTool(repo_dir),
            GitDiffTool(repo_dir),
            GitAddTool(repo_dir),
            GitCommitTool(repo_dir),
        ]
    )


__all__ = [
    "GitStatusTool",
    "GitDiffTool",
    "GitAddTool",
    "GitCommitTool",
    "parse_status",
    "git_registry",
]
