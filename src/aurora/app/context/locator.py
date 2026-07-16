"""Default file locator: rank files by term hits using filesystem tools.

The locator never reads the whole repository. It delegates to the
``search_project`` filesystem tool for each term and aggregates hit counts into
a relevance score, honoring "no direct filesystem access outside filesystem
tools".
"""

from __future__ import annotations

from aurora.app.context.interfaces import FileLocator
from aurora.app.context.models import FileCandidate, QueryPlan
from aurora.app.tools.registry import ToolRegistry

_HITS_PER_TERM_CAP = 50


class SearchFileLocator(FileLocator):
    """Locate files via the ``search_project`` tool and score by term hits."""

    def __init__(self, filesystem: ToolRegistry) -> None:
        self._fs = filesystem

    async def locate(self, plan: QueryPlan, max_files: int) -> list[FileCandidate]:
        hits: dict[str, int] = {}
        matched_terms: dict[str, set[str]] = {}
        for term in plan.terms:
            result = await self._fs.invoke(
                "search_project", {"query": term, "max_results": _HITS_PER_TERM_CAP}
            )
            if not result.ok or result.data is None:
                continue
            for match in result.data["matches"]:
                path = match["path"]
                hits[path] = hits.get(path, 0) + 1
                matched_terms.setdefault(path, set()).add(term)
        candidates = [
            FileCandidate(path=path, score=len(matched_terms[path]) + count / 100.0)
            for path, count in hits.items()
        ]
        # Rank by distinct terms matched, then raw hits; stable by path.
        candidates.sort(key=lambda c: (-c.score, c.path))
        return candidates[:max_files]
