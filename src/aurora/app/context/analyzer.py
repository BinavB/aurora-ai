"""Default query analyzer: distill a query into search terms."""

from __future__ import annotations

import re

from aurora.app.context.interfaces import QueryAnalyzer
from aurora.app.context.models import QueryPlan

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

# Common words that carry little retrieval signal.
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "how",
        "what",
        "why",
        "where",
        "when",
        "does",
        "can",
        "should",
        "add",
        "use",
        "make",
        "get",
        "set",
        "all",
        "any",
        "are",
        "was",
        "have",
        "has",
    }
)


class KeywordQueryAnalyzer(QueryAnalyzer):
    """Extract unique, lower-cased keyword terms from a query."""

    def analyze(self, query: str) -> QueryPlan:
        seen: list[str] = []
        for match in _WORD.findall(query.lower()):
            if match not in _STOPWORDS and match not in seen:
                seen.append(match)
        # Fall back to raw significant words if everything was a stopword.
        if not seen:
            seen = [w for w in query.lower().split() if w][:5]
        return QueryPlan(query=query, terms=seen)
