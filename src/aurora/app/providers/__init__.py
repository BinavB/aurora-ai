"""Providers layer: LLM communication behind one interface.

Every provider inherits :class:`~aurora.app.providers.base.BaseProvider` and
implements :class:`~aurora.app.providers.interface.LLMProvider`. Importing this
package registers all built-in providers. No provider knows about another.
"""

from aurora.app.providers.anthropic import AnthropicProvider
from aurora.app.providers.base import BaseProvider
from aurora.app.providers.cerebras import CerebrasProvider
from aurora.app.providers.gemini import GeminiProvider
from aurora.app.providers.groq import GroqProvider
from aurora.app.providers.interface import LLMProvider
from aurora.app.providers.mistral import MistralProvider
from aurora.app.providers.ollama import OllamaProvider
from aurora.app.providers.openai import OpenAIProvider
from aurora.app.providers.openrouter import OpenRouterProvider
from aurora.app.providers.registry import (
    build_provider,
    register_provider,
    registered_providers,
)
from aurora.app.providers.xai import XAIProvider

__all__ = [
    "LLMProvider",
    "BaseProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "XAIProvider",
    "GeminiProvider",
    "GroqProvider",
    "CerebrasProvider",
    "MistralProvider",
    "OpenRouterProvider",
    "build_provider",
    "register_provider",
    "registered_providers",
]
