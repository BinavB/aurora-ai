"""Shared test helpers.

``mock_client`` builds an :class:`httpx.AsyncClient` backed by a
``MockTransport`` so provider adapters can be exercised without any network.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from aurora.core.config import ProviderConfig
from aurora.core.types import ChatRequest, ChatResponse, Usage
from aurora.providers.base import BaseProvider


class EchoProvider(BaseProvider):
    """A network-free provider that echoes the final message and its context.

    Its reply reports how many messages it received, letting tests assert that
    memory and system prompts are threaded through correctly.
    """

    name = "echo"

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        last = request.messages[-1].content
        return ChatResponse(
            model=request.model,
            content=f"echo[{len(request.messages)}]: {last}",
            usage=Usage(prompt_tokens=len(request.messages), completion_tokens=1),
        )


def echo_provider() -> EchoProvider:
    return EchoProvider(ProviderConfig(base_url="http://echo.local"))


@pytest.fixture
def mock_client() -> Callable[[Callable[[httpx.Request], httpx.Response]], httpx.AsyncClient]:
    def _make(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://test.local",
        )

    return _make
