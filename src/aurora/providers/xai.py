"""xAI (Grok) provider.

xAI exposes an OpenAI-compatible chat completions API, so the request and
response translation is reused wholesale; only the identity differs.
"""

from __future__ import annotations

from aurora.providers.openai import OpenAIProvider
from aurora.providers.registry import register_provider


@register_provider
class XAIProvider(OpenAIProvider):
    """Adapter for the xAI ``/chat/completions`` API."""

    name = "xai"
