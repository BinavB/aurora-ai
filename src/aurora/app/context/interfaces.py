"""Interfaces for the context pipeline stages.

The engine depends on these abstractions so any stage can be replaced (e.g. a
smarter locator or a tokenizer-based compressor) without changing the others.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aurora.app.context.models import (
    ContextChunk,
    ContextRequest,
    FileCandidate,
    QueryPlan,
    Symbol,
)


class QueryAnalyzer(ABC):
    """Stage 1 — understand the request."""

    @abstractmethod
    def analyze(self, query: str) -> QueryPlan:
        """Distill a query into a search plan."""


class FileLocator(ABC):
    """Stage 2 — locate relevant files (via filesystem tools)."""

    @abstractmethod
    async def locate(self, plan: QueryPlan, max_files: int) -> list[FileCandidate]:
        """Return ranked candidate files for the plan."""


class SymbolExtractor(ABC):
    """Stage 3 — extract symbols from a file's content."""

    @abstractmethod
    def extract(self, path: str, content: str) -> list[Symbol]:
        """Return top-level symbols found in ``content``."""


class ContextCompressor(ABC):
    """Stage 4 — compress a file into a token-bounded chunk."""

    @abstractmethod
    def compress(
        self,
        plan: QueryPlan,
        path: str,
        content: str,
        symbols: list[Symbol],
        budget_tokens: int,
    ) -> ContextChunk:
        """Produce a compressed chunk within ``budget_tokens``."""


class PromptBuilder(ABC):
    """Stage 5 — assemble the final prompt messages."""

    @abstractmethod
    def build(
        self, request: ContextRequest, chunks: list[ContextChunk], truncated: bool
    ) -> object:
        """Assemble chunks into a built context."""
