"""The provider abstraction every backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from aurora.core.config import ProviderConfig
from aurora.core.errors import ProviderRequestError
from aurora.core.types import ChatRequest, ChatResponse


class BaseProvider(ABC):
    """Abstract base for chat providers.

    Subclasses translate a provider-agnostic :class:`ChatRequest` into a
    vendor request, perform the call over a shared :class:`httpx.AsyncClient`,
    and translate the vendor reply back into a :class:`ChatResponse`.

    An :class:`httpx.AsyncClient` may be injected (chiefly for testing); when
    omitted one is created lazily and owned by the instance.
    """

    #: Stable, lowercase identifier used by the registry.
    name: str

    def __init__(
        self,
        config: ProviderConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not getattr(self, "name", None):
            raise TypeError(f"{type(self).__name__} must define a class-level 'name'")
        self.config = config
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> httpx.AsyncClient:
        """The HTTP client, created on first use if none was injected."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._client

    async def aclose(self) -> None:
        """Close the HTTP client if this instance created it."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "BaseProvider":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Perform a chat completion, wrapping transport failures uniformly."""
        try:
            return await self._chat(request)
        except httpx.HTTPError as exc:
            raise ProviderRequestError(
                f"{self.name} request failed: {exc}"
            ) from exc

    @abstractmethod
    async def _chat(self, request: ChatRequest) -> ChatResponse:
        """Provider-specific implementation of a chat completion."""
        raise NotImplementedError
