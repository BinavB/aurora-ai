"""Tests for the SSRF-guarded web fetch tool."""

from __future__ import annotations

import httpx

from aurora.app.tools.web import FetchUrlTool, web_registry


def _tool_with(handler) -> FetchUrlTool:
    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return FetchUrlTool(client_factory=factory)


async def test_fetch_url_extracts_readable_text() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            html=(
                "<html><head><title>Docs &amp; Guide</title></head>"
                "<body><script>evil()</script><style>.x{}</style>"
                "<h1>Hello</h1><p>world <b>now</b></p></body></html>"
            ),
        )

    result = await _tool_with(handler).run({"url": "https://example.com/doc"})
    assert result.ok
    assert result.data["title"] == "Docs & Guide"
    assert "Hello world now" in result.data["text"]
    assert "evil()" not in result.data["text"]  # scripts stripped
    assert ".x{}" not in result.data["text"]  # styles stripped


async def test_fetch_url_truncates() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="A" * 500)

    result = await _tool_with(handler).run(
        {"url": "https://example.com", "max_chars": 100}
    )
    assert result.ok
    assert len(result.data["text"]) == 100
    assert result.data["truncated"] is True


async def test_fetch_url_rejects_non_http_scheme() -> None:
    result = await _tool_with(lambda r: httpx.Response(200)).run(
        {"url": "file:///etc/passwd"}
    )
    assert result.ok is False
    assert "http" in result.error["message"].lower()


async def test_fetch_url_blocks_private_addresses() -> None:
    # No client factory -> DNS SSRF guard runs; localhost is loopback -> blocked.
    result = await FetchUrlTool().run({"url": "http://localhost:8000/admin"})
    assert result.ok is False
    assert "non-public" in result.error["message"].lower()


def test_web_registry_exposes_fetch_url() -> None:
    assert web_registry().names() == ("fetch_url",)
