"""Typed input/output models for the filesystem tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PathInput(BaseModel):
    """Input naming a single path relative to the sandbox root."""

    path: str = Field(min_length=1)


class ReadFileOutput(BaseModel):
    """Contents of a file that was read."""

    path: str
    content: str
    size_bytes: int


class WriteFileInput(BaseModel):
    """Input for writing a file."""

    path: str = Field(min_length=1)
    content: str
    overwrite: bool = True


class WriteFileOutput(BaseModel):
    """Result of a write, including any backup created."""

    path: str
    bytes_written: int
    backup: str | None = None


class DeleteFileOutput(BaseModel):
    """Result of a delete."""

    path: str
    deleted: bool


class RenameFileInput(BaseModel):
    """Input for renaming/moving a file within the sandbox."""

    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)


class RenameFileOutput(BaseModel):
    """Result of a rename."""

    src: str
    dst: str


class SearchInput(BaseModel):
    """Input for a project-wide text search."""

    query: str = Field(min_length=1)
    glob: str = "**/*"
    max_results: int = Field(default=100, gt=0, le=1000)


class SearchMatch(BaseModel):
    """A single search hit."""

    path: str
    line: int
    text: str


class RepoMapInput(BaseModel):
    """Input for a project-wide structural map."""

    glob: str = "**/*"
    max_files: int = Field(default=200, gt=0, le=2000)


class RepoMapEntry(BaseModel):
    """One file and its top-level symbols."""

    path: str
    symbols: list[str]


class RepoMapOutput(BaseModel):
    """A structural overview of the project's source files."""

    entries: list[RepoMapEntry]
    rendered: str
    file_count: int
    truncated: bool


class SearchOutput(BaseModel):
    """All matches for a search, with a truncation flag."""

    matches: list[SearchMatch]
    count: int
    truncated: bool
