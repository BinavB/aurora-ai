"""Context layer: the token-efficient retrieval pipeline.

Understands a request, locates relevant files (through filesystem tools),
extracts symbols, compresses to a token budget, and builds provider-ready
prompt messages. Entire repositories are never loaded.
"""

from aurora.app.context.embeddings import Embedder, HashingEmbedder
from aurora.app.context.engine import ContextEngine
from aurora.app.context.models import (
    BuiltContext,
    ContextChunk,
    ContextRequest,
    FileCandidate,
    QueryPlan,
    Symbol,
)
from aurora.app.context.semantic_locator import SemanticFileLocator
from aurora.app.context.vector_index import VectorIndex

__all__ = [
    "ContextEngine",
    "BuiltContext",
    "ContextChunk",
    "ContextRequest",
    "Embedder",
    "FileCandidate",
    "HashingEmbedder",
    "QueryPlan",
    "SemanticFileLocator",
    "Symbol",
    "VectorIndex",
]
