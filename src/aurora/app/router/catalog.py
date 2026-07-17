"""The model catalog.

Holds :class:`ModelProfile` entries and computes availability from
configuration: a model is available if it is local, or its provider has a
configured API key. The default entries are data, not logic — edit freely.
"""

from __future__ import annotations

from typing import Final

from aurora.app.config.models import AppSettings
from aurora.app.router.models import Capability as C
from aurora.app.router.models import ModelProfile

_ALL: Final = frozenset({C.CHAT, C.CODE, C.REASONING, C.VISION, C.LONG_CONTEXT, C.TOOLS})
_TEXT: Final = frozenset({C.CHAT, C.CODE, C.REASONING, C.TOOLS, C.LONG_CONTEXT})
_CODE: Final = frozenset({C.CHAT, C.CODE, C.TOOLS, C.LONG_CONTEXT})

# Every model referenced by the routing chains, plus a local catch-all.
_DEFAULT_MODELS: Final[tuple[ModelProfile, ...]] = (
    # Google Gemini (free tier — flash only; Pro requires billing)
    ModelProfile(
        provider="gemini",
        model="gemini-flash-latest",
        capabilities=_ALL,
        cost_per_1k=0.0,
        latency_ms=300,
    ),
    # Groq (free tier)
    ModelProfile(
        provider="groq",
        model="llama-3.3-70b-versatile",
        capabilities=_TEXT,
        cost_per_1k=0.0,
        latency_ms=120,
    ),
    ModelProfile(
        provider="groq",
        model="openai/gpt-oss-120b",
        capabilities=_TEXT,
        cost_per_1k=0.0,
        latency_ms=200,
    ),
    ModelProfile(  # free vision model — fallback for images when Gemini is busy
        provider="groq",
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        capabilities=frozenset({C.CHAT, C.CODE, C.VISION, C.TOOLS, C.LONG_CONTEXT}),
        cost_per_1k=0.0,
        latency_ms=250,
    ),
    ModelProfile(
        provider="groq",
        model="qwen/qwen3-32b",
        capabilities=_TEXT,
        cost_per_1k=0.0,
        latency_ms=220,
    ),
    # OpenRouter (free variants; needs OPENROUTER_API_KEY)
    ModelProfile(
        provider="openrouter",
        model="meta-llama/llama-3.3-70b-instruct:free",
        capabilities=_TEXT,
        cost_per_1k=0.0,
        latency_ms=500,
    ),
    ModelProfile(
        provider="openrouter",
        model="deepseek/deepseek-r1:free",
        capabilities=_TEXT,
        cost_per_1k=0.0,
        latency_ms=700,
    ),
    # Mistral (free tier)
    ModelProfile(
        provider="mistral",
        model="codestral-latest",
        capabilities=_CODE,
        cost_per_1k=0.0,
        latency_ms=250,
    ),
    # Local Ollama (offline; qwen3/devstral require `ollama pull`)
    ModelProfile(
        provider="ollama",
        model="qwen3:8b",
        capabilities=_CODE,
        cost_per_1k=0.0,
        is_local=True,
        latency_ms=250,
    ),
    ModelProfile(
        provider="ollama",
        model="qwen3:32b",
        capabilities=_TEXT,
        cost_per_1k=0.0,
        is_local=True,
        latency_ms=500,
    ),
    ModelProfile(
        provider="ollama",
        model="devstral",
        capabilities=_CODE,
        cost_per_1k=0.0,
        is_local=True,
        latency_ms=500,
    ),
    ModelProfile(
        provider="ollama",
        model="llama3.2",
        capabilities=_CODE,
        cost_per_1k=0.0,
        is_local=True,
        latency_ms=200,
    ),
)


class ModelCatalog:
    """A queryable collection of model profiles."""

    def __init__(self, models: tuple[ModelProfile, ...]) -> None:
        self._models = models

    def all(self) -> tuple[ModelProfile, ...]:
        """Return every profile."""
        return self._models

    def available(self) -> list[ModelProfile]:
        """Return only profiles marked available."""
        return [m for m in self._models if m.available]


def build_catalog(settings: AppSettings) -> ModelCatalog:
    """Build a catalog whose availability reflects ``settings`` credentials."""
    resolved: list[ModelProfile] = []
    for template in _DEFAULT_MODELS:
        provider = settings.providers.get(template.provider)
        available = template.is_local or bool(provider and provider.api_key)
        resolved.append(template.model_copy(update={"available": available}))
    return ModelCatalog(tuple(resolved))
