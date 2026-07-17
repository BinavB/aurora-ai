"""Cerebras provider.

Cerebras exposes an OpenAI-compatible chat completions API (extremely fast
inference for large open models), so translation is reused from OpenAI.
"""

from __future__ import annotations

from aurora.app.providers.openai import OpenAIProvider
from aurora.app.providers.registry import register_provider


@register_provider
class CerebrasProvider(OpenAIProvider):
    """Adapter for the Cerebras ``/chat/completions`` API."""

    name = "cerebras"
