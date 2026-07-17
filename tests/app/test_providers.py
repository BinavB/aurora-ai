"""Behavioural tests for each provider adapter, using a mock transport."""

from __future__ import annotations

import json

import httpx
import pytest

from aurora.app.config.models import ProviderSettings
from aurora.app.core.events import Event, EventBus
from aurora.app.core.exceptions import (
    ProviderRequestError,
    ProviderResponseError,
    RegistryError,
)
from aurora.app.core.types import ChatRequest, Message, Role
from aurora.app.providers import (
    AnthropicProvider,
    GeminiProvider,
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    XAIProvider,
    build_provider,
    registered_providers,
)
from tests.app.conftest import ClientFactory, echo_provider

SETTINGS = ProviderSettings(base_url="http://test.local", api_key="secret")


def _request() -> ChatRequest:
    return ChatRequest(
        model="m",
        messages=[
            Message(role=Role.SYSTEM, content="be brief"),
            Message(role=Role.USER, content="hello"),
        ],
        max_tokens=32,
    )


# --- registry -------------------------------------------------------------


def test_all_architecture_providers_registered() -> None:
    assert registered_providers() == (
        "anthropic",
        "cerebras",
        "gemini",
        "groq",
        "mistral",
        "ollama",
        "openai",
        "openrouter",
        "xai",
    )


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        ("ollama", OllamaProvider),
        ("openai", OpenAIProvider),
        ("anthropic", AnthropicProvider),
        ("xai", XAIProvider),
        ("gemini", GeminiProvider),
    ],
)
def test_build_provider_returns_expected_class(name: str, cls: type) -> None:
    provider = build_provider(name, SETTINGS)
    assert isinstance(provider, cls)
    assert isinstance(provider, LLMProvider)


def test_build_unknown_provider_raises() -> None:
    with pytest.raises(RegistryError):
        build_provider("nope", SETTINGS)


# --- per-provider round trips --------------------------------------------


async def test_openai_roundtrip(mock_client: ClientFactory) -> None:
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
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

    provider = OpenAIProvider(SETTINGS, client=mock_client(handler))
    result = await provider.chat(_request())
    assert result.content == "hi there"
    assert result.usage.total_tokens == 7
    assert captured["auth"] == "Bearer secret"
    assert captured["body"]["max_tokens"] == 32


async def test_xai_uses_openai_shape(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert str(req.url).endswith("/chat/completions")
        return httpx.Response(
            200, json={"model": "grok", "choices": [{"message": {"content": "yo"}}]}
        )

    result = await XAIProvider(SETTINGS, client=mock_client(handler)).chat(_request())
    assert result.content == "yo"


async def test_ollama_roundtrip(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
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

    result = await OllamaProvider(SETTINGS, client=mock_client(handler)).chat(_request())
    assert result.content == "local reply"
    assert result.usage.total_tokens == 10


async def test_anthropic_hoists_system(mock_client: ClientFactory) -> None:
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

    result = await AnthropicProvider(SETTINGS, client=mock_client(handler)).chat(
        _request()
    )
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
                "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 4},
            },
        )

    result = await GeminiProvider(SETTINGS, client=mock_client(handler)).chat(_request())
    assert result.content == "gem reply"
    assert result.usage.total_tokens == 13


# --- cross-cutting concerns ----------------------------------------------


async def test_gemini_attaches_images(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        parts = body["contents"][-1]["parts"]
        assert any("inlineData" in p for p in parts)
        img = next(p for p in parts if "inlineData" in p)["inlineData"]
        assert img["mimeType"] == "image/png"
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "i see it"}]}}]}
        )

    request = ChatRequest(
        model="gemini-flash-latest",
        messages=[Message(role=Role.USER, content="what is this?")],
        images=["data:image/png;base64,QQ=="],
    )
    result = await GeminiProvider(SETTINGS, client=mock_client(handler)).chat(request)
    assert result.content == "i see it"


async def test_openai_compatible_attaches_images(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        content = json.loads(req.content)["messages"][-1]["content"]
        assert isinstance(content, list)
        assert any(p.get("type") == "image_url" for p in content)
        return httpx.Response(
            200, json={"model": "m", "choices": [{"message": {"content": "ok"}}]}
        )

    request = ChatRequest(
        model="scout",
        messages=[Message(role=Role.USER, content="what is this?")],
        images=["data:image/png;base64,QQ=="],
    )
    result = await OpenAIProvider(SETTINGS, client=mock_client(handler)).chat(request)
    assert result.content == "ok"


async def test_provider_error_never_leaks_url_or_key(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    provider = OpenAIProvider(
        ProviderSettings(base_url="http://secret.local/v1", api_key="sk-leak"),
        client=mock_client(handler),
    )
    with pytest.raises(ProviderRequestError) as excinfo:
        await provider.chat(_request())
    text = str(excinfo.value)
    assert "sk-leak" not in text and "://" not in text
    assert "HTTP 429" in text


async def test_malformed_response_raises(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    provider = OpenAIProvider(SETTINGS, client=mock_client(handler))
    with pytest.raises(ProviderResponseError):
        await provider.chat(_request())


async def test_transport_error_is_wrapped(mock_client: ClientFactory) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    provider = OpenAIProvider(SETTINGS, client=mock_client(handler))
    with pytest.raises(ProviderRequestError):
        await provider.chat(_request())


async def test_chat_emits_events() -> None:
    bus = EventBus()
    events: list[Event] = []

    async def collect(event: Event) -> None:
        events.append(event)

    bus.subscribe("provider.request", collect)
    bus.subscribe("provider.response", collect)

    result = await echo_provider(events=bus).chat(_request())
    names = [e.name for e in events]
    assert names == ["provider.request", "provider.response"]
    # The response event carries the token total.
    assert events[1].payload["total_tokens"] == result.usage.total_tokens
