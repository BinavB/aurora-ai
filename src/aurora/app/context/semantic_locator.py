"""Semantic file locator: retrieve broadly, then re-rank by meaning.

Keyword search finds files that literally mention the query's terms; this
locator then *re-ranks* those candidates by embedding similarity to the whole
natural-language query. This "retrieve-then-rerank" design preserves recall (no
file a keyword would have found is dropped) while adding precision: files whose
content is semantically closest to the request rise to the top, even when they
phrase things differently. Files are read only through the filesystem tools,
honoring the architecture's access rules.
"""

from __future__ import annotations

from aurora.app.context.embeddings import Embedder, HashingEmbedder
from aurora.app.context.interfaces import FileLocator
from aurora.app.context.locator import SearchFileLocator
from aurora.app.context.models import FileCandidate, QueryPlan
from aurora.app.context.vector_index import VectorIndex
from aurora.app.core.logging import get_logger
from aurora.app.tools.registry import ToolRegistry

_logger = get_logger("context.semantic")

_RECALL_FACTOR = 4  # candidates to pull per requested file before re-ranking
_MIN_RECALL = 20  # always consider at least this many candidates
_EMBED_CHARS = 4000  # cap file content fed to the embedder


class SemanticFileLocator(FileLocator):
    """Re-rank a recall locator's candidates by embedding similarity."""

    def __init__(
        self,
        filesystem: ToolRegistry,
        embedder: Embedder | None = None,
        recall: FileLocator | None = None,
    ) -> None:
        self._fs = filesystem
        self._embedder = embedder or HashingEmbedder()
        self._recall = recall or SearchFileLocator(filesystem)

    async def locate(self, plan: QueryPlan, max_files: int) -> list[FileCandidate]:
        pool = await self._recall.locate(
            plan, max(max_files * _RECALL_FACTOR, _MIN_RECALL)
        )
        if not pool:
            return []

        index = VectorIndex()
        for candidate in pool:
            content = await self._read(candidate.path)
            if content is not None:
                index.add(candidate.path, self._embedder.embed(content[:_EMBED_CHARS]))
        if len(index) == 0:
            return pool[:max_files]  # nothing readable: keep recall order

        ranked = index.query(self._embedder.embed(plan.query), max_files)
        if all(score <= 0.0 for _, score in ranked):
            _logger.debug("semantic_no_signal", extra={"query": plan.query})
            return pool[:max_files]  # no semantic signal: keep recall order
        return [FileCandidate(path=path, score=score) for path, score in ranked]

    async def _read(self, path: str) -> str | None:
        result = await self._fs.invoke("read_file", {"path": path})
        if result.ok and result.data is not None:
            return str(result.data["content"])
        return None
