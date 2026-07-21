"""Text embeddings for semantic retrieval.

Provider-independent by design: the default :class:`HashingEmbedder` needs no
network, API key, or heavyweight dependency, so semantic retrieval works fully
offline. It uses the hashing trick over word and character n-gram features, so
morphological variants ("token"/"tokens", "authenticate"/"authentication") land
near each other in vector space — similarity that exact keyword matching misses.
A model-backed embedder can replace it behind this interface for higher fidelity
("vector database later").
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator

Vector = list[float]

_WORD = re.compile(r"[a-z0-9_]+")
_DEFAULT_DIM = 512
_MIN_SUBWORD_LEN = 4  # only sub-tokenize words long enough to benefit
_TRIGRAM_WEIGHT = 0.5  # subword signal, down-weighted vs whole words


class Embedder(ABC):
    """Turn text into a fixed-length, L2-normalized vector."""

    dim: int

    @abstractmethod
    def embed(self, text: str) -> Vector:
        """Embed a single text into a vector of length ``dim``."""

    def embed_all(self, texts: list[str]) -> list[Vector]:
        """Embed many texts (default: one at a time)."""
        return [self.embed(text) for text in texts]


class HashingEmbedder(Embedder):
    """Dependency-free embedder using the hashing trick over n-gram features.

    Stable across processes and machines: features are hashed with BLAKE2b
    rather than Python's per-run-salted :func:`hash`, so the same text always
    yields the same vector — a requirement for a persistable index.
    """

    def __init__(self, dim: int = _DEFAULT_DIM) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def embed(self, text: str) -> Vector:
        vector = [0.0] * self.dim
        for feature, weight in self._features(text):
            bucket, sign = self._hash(feature)
            vector[bucket] += sign * weight
        return _normalize(vector)

    def _features(self, text: str) -> Iterator[tuple[str, float]]:
        """Yield (feature, weight) pairs: whole words plus char trigrams."""
        for word in _WORD.findall(text.lower()):
            yield word, 1.0
            if len(word) >= _MIN_SUBWORD_LEN:
                padded = f"#{word}#"
                for i in range(len(padded) - 2):
                    yield padded[i : i + 3], _TRIGRAM_WEIGHT

    def _hash(self, feature: str) -> tuple[int, float]:
        """Map a feature to a (bucket, sign) via a stable digest."""
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=5).digest()
        value = int.from_bytes(digest, "big")
        sign = 1.0 if value >> 39 & 1 else -1.0  # top bit → sign
        return value % self.dim, sign


def _normalize(vector: Vector) -> Vector:
    """Scale ``vector`` to unit L2 norm (a zero vector is returned unchanged)."""
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


def cosine(left: Vector, right: Vector) -> float:
    """Cosine similarity of two equal-length, L2-normalized vectors."""
    return sum(a * b for a, b in zip(left, right, strict=True))
