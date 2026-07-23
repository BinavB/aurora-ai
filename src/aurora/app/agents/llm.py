"""Helpers for agents that call an LLM through the provider interface.

Agents never perform network I/O themselves; they build provider-agnostic
messages and delegate to an :class:`LLMProvider`. These helpers also parse the
loosely-structured text models tend to return.
"""

from __future__ import annotations

import re

from aurora.app.core.types import ChatRequest, Message, Role
from aurora.app.providers.interface import LLMProvider

_NUMBERED = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+(.*\S)\s*$")


def system(content: str) -> Message:
    """Build a system message."""
    return Message(role=Role.SYSTEM, content=content)


def lead_system(base: str | None, specialized: str) -> Message:
    """Compose the shared engineering prompt with a role-specific one.

    ``base`` is the single-source-of-truth ``AURORA_SYSTEM_PROMPT`` (or ``None``
    when not configured); ``specialized`` is the agent's own instruction. The
    base leads so every agent inherits the same engineering behavior without the
    prompt being copied into each agent.
    """
    return system(f"{base}\n\n{specialized}" if base else specialized)


def user(content: str) -> Message:
    """Build a user message."""
    return Message(role=Role.USER, content=content)


async def complete(
    provider: LLMProvider,
    model: str,
    messages: list[Message],
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    """Request a completion and return its text content."""
    response = await provider.chat(
        ChatRequest(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )
    return response.content


def strip_code_fences(text: str) -> str:
    """Remove a single surrounding Markdown code fence, if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text.strip()
    lines = stripped.splitlines()
    lines = lines[1:]  # drop opening ``` (with optional language)
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_list_items(text: str) -> list[str]:
    """Parse numbered or bulleted list items from ``text``.

    Falls back to a single item containing the whole trimmed text when no list
    markers are present.
    """
    items = [
        match.group(1).strip()
        for line in text.splitlines()
        if (match := _NUMBERED.match(line))
    ]
    if items:
        return items
    trimmed = text.strip()
    return [trimmed] if trimmed else []
