"""Shared plumbing for services that route to a provider with failover."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from aurora.app.core.exceptions import ProviderError, RouterError
from aurora.app.core.logging import get_logger
from aurora.app.core.types import ChatRequest, Message
from aurora.app.providers.base import BaseProvider
from aurora.app.router.models import RoutingDecision, RoutingRequest
from aurora.app.router.router import Router
from aurora.app.services.factory import ProviderFactory

_logger = get_logger("services")

R = TypeVar("R")
Work = Callable[[RoutingDecision, BaseProvider], Awaitable[R]]


class RoutedService:
    """Base providing router-driven execution with automatic failover.

    The router ranks all viable models; each is tried in order until one
    succeeds. A provider error (e.g. quota/402/404) falls through to the next
    candidate, so a single provider's outage never fails the request when an
    alternative exists.
    """

    def __init__(self, router: Router, factory: ProviderFactory) -> None:
        self._router = router
        self._factory = factory

    async def _attempt(
        self, request: RoutingRequest, work: Work[R]
    ) -> tuple[RoutingDecision, R]:
        """Run ``work`` against ranked candidates until one succeeds."""
        decisions = self._router.rank(request)
        if not decisions:
            raise RouterError(
                "No available model satisfies the routing constraints",
                details={"task": request.task},
            )
        last: ProviderError | None = None
        for decision in decisions:
            provider = self._factory.create(decision.provider)
            try:
                return decision, await work(decision, provider)
            except ProviderError as exc:
                last = exc
                _logger.warning(
                    "provider_failover",
                    extra={"provider": decision.provider, "code": exc.code},
                )
            finally:
                await provider.aclose()
        raise last or RouterError("All candidate providers failed")

    async def _complete(
        self,
        request: RoutingRequest,
        messages: list[Message],
        max_tokens: int | None = None,
        images: list[str] | None = None,
    ) -> tuple[RoutingDecision, str]:
        """Route ``messages`` to a model (with failover) and return its text."""

        async def work(decision: RoutingDecision, provider: BaseProvider) -> str:
            response = await provider.chat(
                ChatRequest(
                    model=decision.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=max_tokens,
                    images=images or [],
                )
            )
            return response.content

        return await self._attempt(request, work)
