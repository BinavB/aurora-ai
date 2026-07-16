"""Shared tool-system value objects: permissions, metadata, results."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Permission(StrEnum):
    """A capability a tool requires before it may run."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    GIT = "git"
    NETWORK = "network"


class ToolMetadata(BaseModel):
    """Descriptive metadata every tool advertises.

    Attributes:
        name: Stable, unique tool identifier.
        description: Human-readable summary of what the tool does.
        category: Grouping such as ``filesystem`` or ``git``.
        permissions: Permissions that must be granted to run the tool.
    """

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1)
    permissions: frozenset[Permission] = Field(default_factory=frozenset)


class ToolResult(BaseModel):
    """The structured outcome of a tool invocation.

    Tools never return raw console text; results are always structured, with
    either ``data`` (on success) or ``error`` (on failure) populated.

    Attributes:
        tool: Name of the tool that produced the result.
        ok: Whether the invocation succeeded.
        data: Structured success payload (validated tool output).
        error: Structured error payload (``AuroraError.to_dict()``).
    """

    tool: str
    ok: bool
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
