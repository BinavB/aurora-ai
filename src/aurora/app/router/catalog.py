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

# Default catalog. Costs/latency are indicative defaults, not guarantees.
_DEFAULT_MODELS: Final[tuple[ModelProfile, ...]] = (
    ModelProfile(
        provider="ollama",
        model="llama3.2",
        capabilities=frozenset({C.CHAT, C.CODE}),
        cost_per_1k=0.0,
        is_local=True,
        latency_ms=200,
    ),
    ModelProfile(
        provider="openai",
        model="gpt-4o-mini",
        capabilities=frozenset({C.CHAT, C.CODE, C.TOOLS}),
        cost_per_1k=0.15,
        latency_ms=300,
    ),
    ModelProfile(
        provider="openai",
        model="gpt-4o",
        capabilities=frozenset(
            {C.CHAT, C.CODE, C.REASONING, C.VISION, C.LONG_CONTEXT, C.TOOLS}
        ),
        cost_per_1k=5.0,
        latency_ms=400,
    ),
    ModelProfile(
        provider="anthropic",
        model="claude-sonnet-4",
        capabilities=frozenset({C.CHAT, C.CODE, C.REASONING, C.LONG_CONTEXT, C.TOOLS}),
        cost_per_1k=3.0,
        latency_ms=400,
    ),
    ModelProfile(
        provider="gemini",
        model="gemini-1.5-pro",
        capabilities=frozenset(
            {C.CHAT, C.CODE, C.REASONING, C.VISION, C.LONG_CONTEXT, C.TOOLS}
        ),
        cost_per_1k=3.5,
        latency_ms=450,
    ),
    ModelProfile(
        provider="xai",
        model="grok-2",
        capabilities=frozenset({C.CHAT, C.CODE, C.REASONING, C.TOOLS}),
        cost_per_1k=5.0,
        latency_ms=500,
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
    """Build a catalog whose availability reflects ``settings``.

    Args:
        settings: Application settings holding provider credentials.

    Returns:
        A catalog with each model's ``available`` flag set.
    """
    resolved: list[ModelProfile] = []
    for template in _DEFAULT_MODELS:
        provider = settings.providers.get(template.provider)
        available = template.is_local or bool(provider and provider.api_key)
        resolved.append(template.model_copy(update={"available": available}))
    return ModelCatalog(tuple(resolved))
