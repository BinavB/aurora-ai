"""Provider factory.

Services select a provider *name* via the router, then obtain a live provider
through this factory. The abstraction keeps services decoupled from the
provider registry and makes them trivially testable with fakes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aurora.app.config.models import AppSettings
from aurora.app.core.events import EventBus
from aurora.app.providers.base import BaseProvider
from aurora.app.providers.registry import build_provider


class ProviderFactory(ABC):
    """Creates provider instances by name."""

    @abstractmethod
    def create(self, provider: str) -> BaseProvider:
        """Return a live provider for ``provider`` (caller closes it)."""


class DefaultProviderFactory(ProviderFactory):
    """Build providers from application settings via the registry."""

    def __init__(self, settings: AppSettings, events: EventBus | None = None) -> None:
        self._settings = settings
        self._events = events

    def create(self, provider: str) -> BaseProvider:
        config = self._settings.provider(provider)
        return build_provider(provider, config, events=self._events)
