"""Data models for the context pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aurora.app.core.types import Message


class ContextRequest(BaseModel):
    """A request to build context for a query.

    Attributes:
        query: The natural-language request driving retrieval.
        max_files: Maximum number of files to include.
        max_tokens: Token budget for the assembled context.
        system_prompt: Optional system prompt to lead the built messages.
    """

    query: str = Field(min_length=1)
    max_files: int = Field(default=8, gt=0, le=50)
    max_tokens: int = Field(default=2000, gt=0)
    system_prompt: str | None = None


class QueryPlan(BaseModel):
    """The understood form of a request: search terms distilled from the query."""

    query: str
    terms: list[str]


class FileCandidate(BaseModel):
    """A located file with a relevance score."""

    path: str
    score: float


class Symbol(BaseModel):
    """A top-level code symbol extracted from a file."""

    name: str
    kind: str  # "function" | "class"
    line: int
    signature: str


class ContextChunk(BaseModel):
    """A compressed, token-bounded excerpt of a single file."""

    path: str
    text: str
    symbols: list[Symbol] = Field(default_factory=list)
    tokens: int


class BuiltContext(BaseModel):
    """The final assembled context.

    Attributes:
        messages: Prompt messages ready for a provider.
        token_estimate: Estimated token count of the messages.
        files_used: Paths included in the context.
        truncated: Whether the token budget forced truncation.
    """

    messages: list[Message]
    token_estimate: int
    files_used: list[str]
    truncated: bool
