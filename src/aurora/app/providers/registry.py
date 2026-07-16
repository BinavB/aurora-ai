"""Name-to-class registry for providers.

Concrete providers self-register via the :func:`register_provider` decorator,
so adding a provider never requires editing this module (open/closed).
"""

from __future__ import annotations

import httpx

from aurora.app.config.models import ProviderSettings
from aurora.app.core.events import EventBus
from aurora.app.core.exceptions import ConfigurationError, RegistryError
from aurora.app.providers.base import BaseProvider

_REGISTRY: dict[str, type[BaseProvider]] = {}


def register_provider(cls: type[BaseProvider]) -> type[BaseProvider]:
    """Register a provider class under its ``name`` (usable as a decorator).

    Raises:
        ConfigurationError: If the class defines no ``name``.
    """
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
    settings: ProviderSettings,
    client: httpx.AsyncClient | None = None,
    events: EventBus | None = None,
) -> BaseProvider:
    """Instantiate the provider registered under ``name``.

    Raises:
        RegistryError: If ``name`` is not registered.
    """
    try:
        cls = _REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(registered_providers()) or "<none>"
        raise RegistryError(
            f"Unknown provider '{name}'. Registered: {known}",
            details={"requested": name},
        ) from exc
    return cls(settings, client=client, events=events)
