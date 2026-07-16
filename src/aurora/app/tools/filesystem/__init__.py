"""Filesystem tools: the only sanctioned path to the filesystem.

Per the architecture, no other layer touches files directly. Every tool is
sandboxed to a project root, normalizes paths, prevents traversal, writes
atomically, and backs up files before overwriting them.
"""

from aurora.app.tools.filesystem.paths import PathSandbox
from aurora.app.tools.filesystem.tools import (
    DeleteFileTool,
    ReadFileTool,
    RenameFileTool,
    SearchProjectTool,
    WriteFileTool,
)
from aurora.app.tools.registry import ToolRegistry


def filesystem_registry(root: str) -> ToolRegistry:
    """Build a registry of the filesystem tools sandboxed to ``root``.

    Args:
        root: Project root that bounds every filesystem operation.

    Returns:
        A registry containing the read/write/delete/rename/search tools.
    """
    return ToolRegistry(
        [
            ReadFileTool(root),
            WriteFileTool(root),
            DeleteFileTool(root),
            RenameFileTool(root),
            SearchProjectTool(root),
        ]
    )


__all__ = [
    "PathSandbox",
    "ReadFileTool",
    "WriteFileTool",
    "DeleteFileTool",
    "RenameFileTool",
    "SearchProjectTool",
    "filesystem_registry",
]
