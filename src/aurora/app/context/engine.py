"""The context engine: orchestrates the retrieval pipeline.

Pipeline: understand → locate → (read via tools) → extract symbols → compress →
build prompt. Files are read only through the filesystem tools, and the token
budget bounds the assembled context so entire repositories are never loaded.
"""

from __future__ import annotations

from aurora.app.context.analyzer import KeywordQueryAnalyzer
from aurora.app.context.builder import MessagePromptBuilder
from aurora.app.context.compressor import SymbolAwareCompressor
from aurora.app.context.extractor import PythonSymbolExtractor
from aurora.app.context.interfaces import (
    ContextCompressor,
    FileLocator,
    PromptBuilder,
    QueryAnalyzer,
    SymbolExtractor,
)
from aurora.app.context.models import (
    BuiltContext,
    ContextChunk,
    ContextRequest,
    FileCandidate,
    QueryPlan,
)
from aurora.app.context.semantic_locator import SemanticFileLocator
from aurora.app.core.logging import get_logger
from aurora.app.tools.registry import ToolRegistry

_logger = get_logger("context")


class ContextEngine:
    """Compose the pipeline stages into a single ``build`` operation."""

    def __init__(
        self,
        filesystem: ToolRegistry,
        analyzer: QueryAnalyzer | None = None,
        locator: FileLocator | None = None,
        extractor: SymbolExtractor | None = None,
        compressor: ContextCompressor | None = None,
        builder: PromptBuilder | None = None,
    ) -> None:
        self._fs = filesystem
        self._analyzer = analyzer or KeywordQueryAnalyzer()
        self._locator = locator or SemanticFileLocator(filesystem)
        self._extractor = extractor or PythonSymbolExtractor()
        self._compressor = compressor or SymbolAwareCompressor()
        self._builder = builder or MessagePromptBuilder()

    async def build(self, request: ContextRequest) -> BuiltContext:
        """Run the pipeline and return the assembled context."""
        plan = self._analyzer.analyze(request.query)
        candidates = await self._locator.locate(plan, request.max_files)
        chunks, truncated = await self._gather_chunks(
            plan, candidates, request.max_tokens
        )
        built = self._builder.build(request, chunks, truncated)
        _logger.info(
            "context_built",
            extra={
                "files": len(built.files_used),
                "tokens": built.token_estimate,
                "truncated": built.truncated,
            },
        )
        return built

    async def _gather_chunks(
        self, plan: QueryPlan, candidates: list[FileCandidate], budget: int
    ) -> tuple[list[ContextChunk], bool]:
        chunks: list[ContextChunk] = []
        remaining = budget
        for candidate in candidates:
            if remaining <= 0:
                return chunks, True
            content = await self._read(candidate.path)
            if content is None:
                continue
            symbols = self._extractor.extract(candidate.path, content)
            chunk = self._compressor.compress(
                plan, candidate.path, content, symbols, remaining
            )
            if chunk.tokens == 0:
                continue
            chunks.append(chunk)
            remaining -= chunk.tokens
        return chunks, remaining <= 0

    async def _read(self, path: str) -> str | None:
        result = await self._fs.invoke("read_file", {"path": path})
        if result.ok and result.data is not None:
            return str(result.data["content"])
        return None
