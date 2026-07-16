"""Tools layer: sandboxed capabilities behind a single abstraction.

Every tool implements :class:`~aurora.tools.base.BaseTool`. The registry maps
tool names to instances so callers can discover and invoke tools by name.
"""

from aurora.tools.base import BaseTool, ToolResult
from aurora.tools.fs import ListDirTool, ReadFileTool, WriteFileTool
from aurora.tools.registry import ToolRegistry, default_registry

__all__ = [
    "BaseTool",
    "ToolResult",
    "ListDirTool",
    "ReadFileTool",
    "WriteFileTool",
    "ToolRegistry",
    "default_registry",
]
