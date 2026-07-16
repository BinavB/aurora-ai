"""Instance registry for tools."""

from __future__ import annotations

from aurora.core.errors import ConfigurationError
from aurora.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """A collection of tools addressable by name."""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: BaseTool) -> BaseTool:
        """Add a tool, rejecting duplicate names."""
        if tool.name in self._tools:
            raise ConfigurationError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> BaseTool:
        """Return the tool registered under ``name`` or raise."""
        try:
            return self._tools[name]
        except KeyError as exc:
            known = ", ".join(self.names()) or "<none>"
            raise ConfigurationError(
                f"Unknown tool '{name}'. Registered: {known}"
            ) from exc

    def names(self) -> tuple[str, ...]:
        """Return the sorted names of all registered tools."""
        return tuple(sorted(self._tools))

    def specs(self) -> list[dict[str, object]]:
        """Return every tool's public schema, ordered by name."""
        return [self._tools[name].spec() for name in self.names()]

    async def invoke(self, name: str, **kwargs: object) -> ToolResult:
        """Look up and run a tool by name."""
        return await self.get(name).run(**kwargs)


def default_registry(root: str) -> ToolRegistry:
    """Build a registry of the built-in filesystem tools sandboxed to ``root``."""
    from aurora.tools.fs import ListDirTool, ReadFileTool, WriteFileTool

    return ToolRegistry(
        [ReadFileTool(root), WriteFileTool(root), ListDirTool(root)]
    )
