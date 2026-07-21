"""In-memory vector index: cosine top-k over embedded documents.

A minimal, dependency-free store so semantic retrieval works without a vector
database. It holds vectors keyed by document id and answers nearest-neighbor
queries by cosine similarity. A persistent or approximate-nearest-neighbor
backend (SQLite, FAISS, a hosted vector DB) can replace it behind this same
small surface — "SQLite first, vector database later".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aurora.app.context.embeddings import Vector, cosine


@dataclass
class VectorIndex:
    """Cosine-similarity nearest-neighbor store keyed by document id."""

    _ids: list[str] = field(default_factory=list)
    _vectors: list[Vector] = field(default_factory=list)

    def add(self, doc_id: str, vector: Vector) -> None:
        """Index ``vector`` under ``doc_id``."""
        self._ids.append(doc_id)
        self._vectors.append(vector)

    def __len__(self) -> int:
        return len(self._ids)

    def query(self, vector: Vector, k: int) -> list[tuple[str, float]]:
        """Return up to ``k`` (doc_id, similarity) pairs, most similar first.

        Ties break by ``doc_id`` so results are deterministic.
        """
        if k <= 0 or not self._ids:
            return []
        scored = [
            (doc_id, cosine(vector, candidate))
            for doc_id, candidate in zip(self._ids, self._vectors, strict=True)
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:k]
