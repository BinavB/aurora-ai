"""OpenRouter provider.

OpenRouter exposes an OpenAI-compatible chat completions API that proxies many
models (including free variants), so translation is reused from OpenAI.
"""

from __future__ import annotations

from aurora.app.providers.openai import OpenAIProvider
from aurora.app.providers.registry import register_provider


@register_provider
class OpenRouterProvider(OpenAIProvider):
    """Adapter for the OpenRouter ``/chat/completions`` API."""

    name = "openrouter"
