"""Instance registry for tools."""

from __future__ import annotations

from typing import Any

from aurora.app.core.exceptions import ConfigurationError, RegistryError
from aurora.app.tools.base import BaseTool
from aurora.app.tools.models import Permission, ToolResult


class ToolRegistry:
    """A collection of tools addressable by name."""

    def __init__(self, tools: list[BaseTool[Any, Any]] | None = None) -> None:
        self._tools: dict[str, BaseTool[Any, Any]] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: BaseTool[Any, Any]) -> BaseTool[Any, Any]:
        """Add a tool, rejecting duplicate names.

        Raises:
            ConfigurationError: If a tool with the same name exists.
        """
        if tool.name in self._tools:
            raise ConfigurationError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> BaseTool[Any, Any]:
        """Return the tool registered under ``name``.

        Raises:
            RegistryError: If no such tool is registered.
        """
        try:
            return self._tools[name]
        except KeyError as exc:
            known = ", ".join(self.names()) or "<none>"
            raise RegistryError(
                f"Unknown tool '{name}'. Registered: {known}",
                details={"requested": name},
            ) from exc

    def names(self) -> tuple[str, ...]:
        """Return the sorted names of all registered tools."""
        return tuple(sorted(self._tools))

    def specs(self) -> list[dict[str, Any]]:
        """Return every tool's public schema, ordered by name."""
        return [self._tools[name].spec() for name in self.names()]

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        granted: frozenset[Permission] | None = None,
    ) -> ToolResult:
        """Look up and run a tool by name with the given permissions."""
        return await self.get(name).run(arguments, granted=granted)
