"""Lightweight token estimation.

A cheap, provider-agnostic heuristic (~4 characters per token) sufficient for
budgeting context. It intentionally avoids a tokenizer dependency; callers that
need exact counts can substitute one behind the same functions.
"""

from __future__ import annotations

from collections.abc import Iterable

from aurora.app.core.types import Message

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate the token count of ``text`` (minimum 1 for non-empty text)."""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def estimate_messages(messages: Iterable[Message]) -> int:
    """Estimate the combined token count of ``messages``."""
    return sum(estimate_tokens(message.content) for message in messages)
