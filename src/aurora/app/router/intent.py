"""Lightweight intent classification for conversational (chat) messages.

Chat text is mapped to a :class:`TaskKind` so the router can pick the right
fallback chain. Plan/Review/Implement come from explicit UI modes, not text.
"""

from __future__ import annotations

from aurora.app.router.models import TaskKind

_SUMMARIZE_HINTS = (
    "summarize",
    "summarise",
    "summary",
    "tl;dr",
    "tldr",
    "condense",
    "recap",
)
_EXPLAIN_HINTS = (
    "explain",
    "what is",
    "what are",
    "how does",
    "how do",
    "why does",
    "why is",
    "teach me",
    "eli5",
)


def classify_intent(text: str) -> TaskKind:
    """Classify chat ``text`` into CHAT, SUMMARIZE, or EXPLAIN."""
    lowered = text.lower()
    if any(hint in lowered for hint in _SUMMARIZE_HINTS):
        return TaskKind.SUMMARIZE
    if any(hint in lowered for hint in _EXPLAIN_HINTS):
        return TaskKind.EXPLAIN
    return TaskKind.CHAT
