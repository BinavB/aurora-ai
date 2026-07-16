"""Tools layer: everything external is a Tool.

Each tool exposes typed input/output schemas, metadata, validation, and
permission requirements, and returns structured data only — never raw console
output. The registry discovers and invokes tools by name.
"""

from aurora.app.tools.base import BaseTool
from aurora.app.tools.models import Permission, ToolMetadata, ToolResult
from aurora.app.tools.registry import ToolRegistry

__all__ = [
    "BaseTool",
    "Permission",
    "ToolMetadata",
    "ToolResult",
    "ToolRegistry",
]
