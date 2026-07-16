"""Providers layer: concrete adapters behind a single abstraction.

Every provider implements :class:`~aurora.providers.base.BaseProvider`. The
:mod:`registry` maps provider names to classes so callers can select a backend
by name without importing it directly.
"""

from aurora.providers.anthropic import AnthropicProvider
from aurora.providers.base import BaseProvider
from aurora.providers.gemini import GeminiProvider
from aurora.providers.ollama import OllamaProvider
from aurora.providers.openai import OpenAIProvider
from aurora.providers.registry import build_provider, register_provider, registered_providers
from aurora.providers.xai import XAIProvider

__all__ = [
    "BaseProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "XAIProvider",
    "GeminiProvider",
    "build_provider",
    "register_provider",
    "registered_providers",
]
