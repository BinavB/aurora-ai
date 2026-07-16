"""The tool abstraction every capability implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class ToolResult(BaseModel):
    """The outcome of a tool invocation."""

    ok: bool
    output: str


class BaseTool(ABC):
    """Abstract base for tools.

    A tool advertises a stable ``name``, a human-readable ``description``, and
    a JSON-schema ``parameters`` object describing its inputs. Implementations
    run asynchronously and must translate failures into a failed
    :class:`ToolResult` rather than raising.
    """

    name: str
    description: str
    parameters: dict[str, object]

    def __init__(self) -> None:
        for attr in ("name", "description", "parameters"):
            if not getattr(self, attr, None):
                raise TypeError(f"{type(self).__name__} must define '{attr}'")

    def spec(self) -> dict[str, object]:
        """Return the tool's public schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    @abstractmethod
    async def run(self, **kwargs: object) -> ToolResult:
        """Execute the tool with keyword arguments matching ``parameters``."""
        raise NotImplementedError
