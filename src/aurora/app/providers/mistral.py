"""Mistral provider (Codestral and chat models).

Mistral exposes an OpenAI-compatible chat completions API, so translation is
reused from OpenAI.
"""

from __future__ import annotations

from aurora.app.providers.openai import OpenAIProvider
from aurora.app.providers.registry import register_provider


@register_provider
class MistralProvider(OpenAIProvider):
    """Adapter for the Mistral ``/chat/completions`` API."""

    name = "mistral"
