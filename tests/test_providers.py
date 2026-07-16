"""Behavioural tests for each provider adapter, using a mock transport."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from aurora.core import ChatRequest, Message, ProviderConfig, ProviderResponseError, Role
from aurora.providers.anthropic import AnthropicProvider
from aurora.providers.gemini import GeminiProvider
from aurora.providers.ollama import OllamaProvider
from aurora.providers.openai import OpenAIProvider
from aurora.providers.xai import XAIProvider

ClientFactory = Callable[[Callable[[httpx.Request], httpx.Response]], httpx.AsyncClient]

CONFIG = ProviderConfig(base_url="http://test.local", api_key="secret")


def _request() -> ChatRequest:
    return ChatRequest(
        model="m",
        messages=[
            Message(role=Role.SYSTEM, content="be brief"),
            Message(role=Role.USER, content="hello"),
        ],
        max_tokens=32,
    )


async def test_openai_chat_roundtrip(mock_client: ClientFactory) -> None:
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-x",
                "choices": [{"message": {"content": "hi there"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )

    provider = OpenAIProvider(CONFIG, client=mock_client(handler))
    result = await provider.chat(_request())

    assert result.content == "hi there"
    assert result.usage.total_tokens == 7
    assert captured["url"].endswith("/chat/completions")
    assert captured["auth"] == "Bearer secret"
    assert captured["body"]["max_tokens"] == 32


async def test_xai_uses_openai_shape(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert str(req.url).endswith("/chat/completions")
        return httpx.Response(
            200,
            json={"model": "grok", "choices": [{"message": {"content": "yo"}}]},
        )

    provider = XAIProvider(CONFIG, client=mock_client(handler))
    result = await provider.chat(_request())
    assert result.content == "yo"


async def test_ollama_chat_roundtrip(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert str(req.url).endswith("/api/chat")
        assert json.loads(req.content)["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": "llama",
                "message": {"role": "assistant", "content": "local reply"},
                "prompt_eval_count": 4,
                "eval_count": 6,
            },
        )

    provider = OllamaProvider(CONFIG, client=mock_client(handler))
    result = await provider.chat(_request())
    assert result.content == "local reply"
    assert result.usage.total_tokens == 10


async def test_anthropic_hoists_system_prompt(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body["system"] == "be brief"
        assert all(m["role"] != "system" for m in body["messages"])
        assert req.headers.get("x-api-key") == "secret"
        return httpx.Response(
            200,
            json={
                "model": "claude",
                "content": [{"type": "text", "text": "brief answer"}],
                "usage": {"input_tokens": 8, "output_tokens": 3},
            },
        )

    provider = AnthropicProvider(CONFIG, client=mock_client(handler))
    result = await provider.chat(_request())
    assert result.content == "brief answer"
    assert result.usage.total_tokens == 11


async def test_gemini_maps_roles_and_system(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert ":generateContent" in str(req.url)
        assert req.url.params.get("key") == "secret"
        body = json.loads(req.content)
        assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
        assert body["contents"][0]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "modelVersion": "gemini-x",
                "candidates": [{"content": {"parts": [{"text": "gem reply"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 9,
                    "candidatesTokenCount": 4,
                },
            },
        )

    provider = GeminiProvider(CONFIG, client=mock_client(handler))
    result = await provider.chat(_request())
    assert result.content == "gem reply"
    assert result.usage.total_tokens == 13


async def test_malformed_response_raises(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    provider = OpenAIProvider(CONFIG, client=mock_client(handler))
    with pytest.raises(ProviderResponseError):
        await provider.chat(_request())
