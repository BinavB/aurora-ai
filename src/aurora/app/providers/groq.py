"""Groq provider.

Groq exposes an OpenAI-compatible chat completions API (very fast inference),
so request and response translation is reused wholesale; only the identity
differs.
"""

from __future__ import annotations

from aurora.app.providers.openai import OpenAIProvider
from aurora.app.providers.registry import register_provider


@register_provider
class GroqProvider(OpenAIProvider):
    """Adapter for the Groq ``/chat/completions`` API."""

    name = "groq"
