from __future__ import annotations

import json

import httpx
import pytest

from aurora.app.search import (
    TavilySearch,
    WebSearchError,
    format_results,
    needs_web_search,
    search_query,
)
from aurora.app.search.tavily import SearchResult, parse_results


def test_parse_results_strips_markup_and_skips_incomplete_items() -> None:
    payload = {
        "results": [
            {
                "title": "<b>Rain</b> news",
                "url": "https://a.test",
                "content": "Heavy <b>rain</b>  now.",
            },
            {"title": "No link"},
        ]
    }
    assert parse_results(payload) == [
        SearchResult("Rain news", "https://a.test", "Heavy rain now.")
    ]


def test_parse_results_handles_missing_results() -> None:
    assert parse_results({}) == []
    assert format_results([]) == "The web search found no results for this question."


def test_format_results_numbers_each_source() -> None:
    text = format_results([SearchResult("A", "https://a.test", "Note")])
    assert text == "1. A (https://a.test)\nNote"


@pytest.mark.parametrize(
    "message,expected",
    [
        ("what is the latest news on rain", True),
        ("search for kerala weather", True),
        ("what is the price of gold today", True),
        ("write a poem about the sea", False),
        ("explain recursion", False),
    ],
)
def test_needs_web_search_detects_live_questions(message: str, expected: bool) -> None:
    assert needs_web_search(message) is expected


def test_search_query_drops_the_search_prefix() -> None:
    assert search_query("search for kerala weather") == "kerala weather"
    assert search_query("latest news") == "latest news"


async def test_tavily_search_sends_key_and_parses_results() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"results": [{"title": "T", "url": "https://t.test", "content": "D"}]},
        )

    search = TavilySearch(
        "key-1",
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    results = await search.search("gold price")

    assert seen["auth"] == "Bearer key-1"
    assert seen["body"]["query"] == "gold price"
    assert results == [SearchResult("T", "https://t.test", "D")]


async def test_tavily_search_raises_on_bad_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={})

    search = TavilySearch(
        "bad",
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(WebSearchError):
        await search.search("anything")


def test_creator_questions_search_the_creator_name() -> None:
    assert needs_web_search("who is binav?")
    assert search_query("what does binav do") == "binav.b"


async def test_chat_reply_carries_the_sources_used() -> None:
    from aurora.app.database import Database
    from aurora.app.memory import MemoryStore
    from aurora.app.services import ChatService
    from tests.app.test_services import FakeFactory, _CapturingProvider, _router

    class _Search:
        async def search(self, query: str, count: int = 5) -> list[SearchResult]:
            return [SearchResult("Binav", "https://binav.test", "Profile")]

    store = MemoryStore(Database())
    await store.open()
    service = ChatService(
        _router(), FakeFactory(_CapturingProvider()), store, search=_Search()
    )
    reply = await service.chat("s", "who is binav")
    assert reply.sources == [SearchResult("Binav", "https://binav.test", "Profile")]
