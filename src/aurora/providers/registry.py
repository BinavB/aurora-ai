"""Name-to-class registry for providers."""

from __future__ import annotations

import httpx

from aurora.core.config import ProviderConfig
from aurora.core.errors import ConfigurationError
from aurora.providers.base import BaseProvider

_REGISTRY: dict[str, type[BaseProvider]] = {}


def register_provider(cls: type[BaseProvider]) -> type[BaseProvider]:
    """Register a provider class under its ``name``. Usable as a decorator."""
    name = getattr(cls, "name", None)
    if not name:
        raise ConfigurationError(f"{cls.__name__} has no 'name' to register")
    _REGISTRY[name] = cls
    return cls


def registered_providers() -> tuple[str, ...]:
    """Return the sorted names of all registered providers."""
    return tuple(sorted(_REGISTRY))


def build_provider(
    name: str,
    config: ProviderConfig,
    client: httpx.AsyncClient | None = None,
) -> BaseProvider:
    """Instantiate the provider registered under ``name``."""
    try:
        cls = _REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(registered_providers()) or "<none>"
        raise ConfigurationError(
            f"Unknown provider '{name}'. Registered: {known}"
        ) from exc
    return cls(config, client=client)
