"""The abstract base every provider inherits from.

``BaseProvider`` owns the cross-cutting concerns — HTTP client lifecycle,
uniform error wrapping, structured logging, and event emission — so concrete
providers implement only vendor request/response translation.
"""

from __future__ import annotations

import httpx

from aurora.app.config.models import ProviderSettings
from aurora.app.core.events import Event, EventBus
from aurora.app.core.exceptions import ProviderRequestError
from aurora.app.core.logging import get_logger
from aurora.app.core.types import ChatRequest, ChatResponse


class BaseProvider:
    """Base class for LLM providers.

    Args:
        settings: Connection settings for this provider.
        client: Optional injected HTTP client (chiefly for testing). When
            omitted, one is created lazily and owned by the instance.
        events: Optional event bus for request/response telemetry.
    """

    name: str

    def __init__(
        self,
        settings: ProviderSettings,
        client: httpx.AsyncClient | None = None,
        events: EventBus | None = None,
    ) -> None:
        if not getattr(self, "name", None):
            raise TypeError(f"{type(self).__name__} must define a class-level 'name'")
        self._settings = settings
        self._client = client
        self._owns_client = client is None
        self._events = events
        self._logger = get_logger(f"providers.{self.name}")

    @property
    def settings(self) -> ProviderSettings:
        """The provider's connection settings."""
        return self._settings

    @property
    def client(self) -> httpx.AsyncClient:
        """The HTTP client, created on first use if none was injected."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.base_url,
                timeout=self._settings.timeout,
            )
        return self._client

    async def aclose(self) -> None:
        """Close the HTTP client if this instance created it."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BaseProvider:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Perform a chat completion with uniform logging and error handling."""
        await self._emit("provider.request", model=request.model)
        self._logger.info("chat_request", extra={"model": request.model})
        try:
            response = await self._chat(request)
        except httpx.HTTPError as exc:
            self._logger.error("chat_transport_error", extra={"model": request.model})
            raise ProviderRequestError(
                f"{self.name} request failed: {exc}",
                details={"provider": self.name, "model": request.model},
            ) from exc
        await self._emit(
            "provider.response",
            model=response.model,
            total_tokens=response.usage.total_tokens,
        )
        self._logger.info(
            "chat_response",
            extra={"model": response.model, "total_tokens": response.usage.total_tokens},
        )
        return response

    async def _emit(self, name: str, **payload: object) -> None:
        if self._events is not None:
            await self._events.publish(Event(name=name, payload=dict(payload)))

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        """Vendor-specific completion. Implemented by subclasses."""
        raise NotImplementedError
