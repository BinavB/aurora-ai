"""Context layer: the token-efficient retrieval pipeline.

Understands a request, locates relevant files (through filesystem tools),
extracts symbols, compresses to a token budget, and builds provider-ready
prompt messages. Entire repositories are never loaded.
"""

from aurora.app.context.engine import ContextEngine
from aurora.app.context.models import (
    BuiltContext,
    ContextChunk,
    ContextRequest,
    FileCandidate,
    QueryPlan,
    Symbol,
)

__all__ = [
    "ContextEngine",
    "BuiltContext",
    "ContextChunk",
    "ContextRequest",
    "FileCandidate",
    "QueryPlan",
    "Symbol",
]
