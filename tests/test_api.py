"""Tests for the API layer, driven over ASGI without a live server."""

from __future__ import annotations

import httpx
import pytest

from aurora.api import create_app
from aurora.core.config import ProviderConfig, Settings
from aurora.tools.registry import default_registry
from tests.conftest import EchoProvider


@pytest.fixture
def client(tmp_path) -> httpx.AsyncClient:
    settings = Settings(providers={"echo": ProviderConfig(base_url="http://echo.local")})
    app = create_app(
        settings=settings,
        tools=default_registry(str(tmp_path)),
        provider_factory=lambda name, config: EchoProvider(config),
    )
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health(client: httpx.AsyncClient) -> None:
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_providers_lists_registered(client: httpx.AsyncClient) -> None:
    res = await client.get("/providers")
    assert "anthropic" in res.json()["providers"]


async def test_chat_threads_memory(client: httpx.AsyncClient) -> None:
    body = {"session_id": "s", "provider": "echo", "model": "m", "message": "hi"}
    first = (await client.post("/chat", json=body)).json()
    assert first["content"] == "echo[1]: hi"

    body["message"] = "again"
    second = (await client.post("/chat", json=body)).json()
    assert second["content"] == "echo[3]: again"


async def test_chat_unknown_provider_is_400(client: httpx.AsyncClient) -> None:
    body = {"session_id": "s", "provider": "ghost", "model": "m", "message": "hi"}
    res = await client.post("/chat", json=body)
    assert res.status_code == 400


async def test_tools_list_and_invoke(client: httpx.AsyncClient) -> None:
    listed = (await client.get("/tools")).json()["tools"]
    assert {t["name"] for t in listed} == {"read_file", "write_file", "list_dir"}

    res = await client.post(
        "/tools/write_file",
        json={"arguments": {"path": "x.txt", "content": "hi"}},
    )
    assert res.status_code == 200 and res.json()["ok"] is True


async def test_unknown_tool_is_404(client: httpx.AsyncClient) -> None:
    res = await client.post("/tools/ghost", json={"arguments": {}})
    assert res.status_code == 404


async def test_index_serves_frontend(client: httpx.AsyncClient) -> None:
    res = await client.get("/")
    assert res.status_code == 200
    assert "AURORA AI" in res.text
