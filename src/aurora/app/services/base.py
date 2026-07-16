"""Shared plumbing for services that route to a provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aurora.app.providers.base import BaseProvider
from aurora.app.router.models import RoutingDecision, RoutingRequest
from aurora.app.router.router import Router
from aurora.app.services.factory import ProviderFactory


class RoutedService:
    """Base providing router-driven provider acquisition with cleanup."""

    def __init__(self, router: Router, factory: ProviderFactory) -> None:
        self._router = router
        self._factory = factory

    @asynccontextmanager
    async def _routed(
        self, request: RoutingRequest
    ) -> AsyncIterator[tuple[RoutingDecision, BaseProvider]]:
        """Route the request, yield ``(decision, provider)``, then close it."""
        decision = self._router.route(request)
        provider = self._factory.create(decision.provider)
        try:
            yield decision, provider
        finally:
            await provider.aclose()
