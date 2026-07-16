"""Shared fixtures for AEGIS-architecture (``aurora.app``) tests."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from aurora.app.config.models import ProviderSettings
from aurora.app.core.types import ChatRequest, ChatResponse, Usage
from aurora.app.providers.base import BaseProvider

ClientFactory = Callable[[Callable[[httpx.Request], httpx.Response]], httpx.AsyncClient]


class EchoProvider(BaseProvider):
    """A network-free provider that echoes its context size and last message."""

    name = "echo"

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        last = request.messages[-1].content
        return ChatResponse(
            model=request.model,
            content=f"echo[{len(request.messages)}]: {last}",
            usage=Usage(prompt_tokens=len(request.messages), completion_tokens=1),
        )


def echo_provider(**kwargs: object) -> EchoProvider:
    return EchoProvider(ProviderSettings(base_url="http://echo.local"), **kwargs)


class ScriptedProvider(BaseProvider):
    """A provider that returns a fixed, pre-scripted reply regardless of input.

    Useful for testing agents that parse structured text from a model.
    """

    name = "scripted"

    def __init__(self, reply: str) -> None:
        super().__init__(ProviderSettings(base_url="http://scripted.local"))
        self._reply = reply

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(model=request.model, content=self._reply)


@pytest.fixture
def mock_client() -> ClientFactory:
    def _make(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://test.local"
        )

    return _make
