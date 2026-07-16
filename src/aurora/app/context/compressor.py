"""Default compressor: reduce a file to symbols plus matching lines.

Instead of embedding whole files, a chunk contains the file's symbol
signatures and the lines that mention query terms, trimmed to fit the token
budget. This keeps context small and relevant.
"""

from __future__ import annotations

from aurora.app.context.interfaces import ContextCompressor
from aurora.app.context.models import ContextChunk, QueryPlan, Symbol
from aurora.app.context.tokens import estimate_tokens

_MAX_SYMBOLS = 20
_MAX_MATCH_LINES = 40


class SymbolAwareCompressor(ContextCompressor):
    """Compose a compact excerpt from symbols and term-matching lines."""

    def compress(
        self,
        plan: QueryPlan,
        path: str,
        content: str,
        symbols: list[Symbol],
        budget_tokens: int,
    ) -> ContextChunk:
        if budget_tokens <= 0:
            return ContextChunk(path=path, text="", symbols=[], tokens=0)
        parts = [f"# {path}"]
        parts.extend(self._symbol_lines(symbols))
        parts.extend(self._match_lines(plan, content))
        text = "\n".join(parts)
        tokens = estimate_tokens(text)
        if tokens > budget_tokens:
            text = text[: budget_tokens * 4].rstrip()
            tokens = estimate_tokens(text)
        return ContextChunk(
            path=path, text=text, symbols=symbols[:_MAX_SYMBOLS], tokens=tokens
        )

    @staticmethod
    def _symbol_lines(symbols: list[Symbol]) -> list[str]:
        if not symbols:
            return []
        lines = ["symbols:"]
        lines.extend(f"  L{s.line}: {s.signature}" for s in symbols[:_MAX_SYMBOLS])
        return lines

    @staticmethod
    def _match_lines(plan: QueryPlan, content: str) -> list[str]:
        matches = []
        for number, line in enumerate(content.splitlines(), start=1):
            lowered = line.lower()
            if any(term in lowered for term in plan.terms):
                matches.append(f"  L{number}: {line.strip()}")
                if len(matches) >= _MAX_MATCH_LINES:
                    break
        return ["matches:", *matches] if matches else []
