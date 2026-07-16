"""Typed models for git tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StatusEntry(BaseModel):
    """A single changed path from ``git status``.

    Attributes:
        code: Two-character porcelain status code (e.g. ``??``, ``M ``).
        path: The affected path (destination path for renames).
    """

    code: str
    path: str


class GitStatusOutput(BaseModel):
    """Working-tree status."""

    entries: list[StatusEntry]
    clean: bool


class GitDiffInput(BaseModel):
    """Input for a diff request."""

    staged: bool = False
    path: str | None = None


class GitDiffOutput(BaseModel):
    """A unified diff."""

    diff: str
    has_changes: bool


class GitAddInput(BaseModel):
    """Input for staging paths."""

    paths: list[str] = Field(min_length=1)


class GitAddOutput(BaseModel):
    """Result of staging."""

    staged: list[str]


class GitCommitInput(BaseModel):
    """Input for committing staged changes.

    ``approve`` must be ``True``; commits never happen implicitly.
    """

    message: str = Field(min_length=1)
    approve: bool = False


class GitCommitOutput(BaseModel):
    """Result of a commit."""

    committed: bool
    ref: str
