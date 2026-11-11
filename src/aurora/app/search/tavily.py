from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from aurora.app.core.exceptions import AuroraError

TAVILY_ENDPOINT = "https://api.tavily.com/search"
DEFAULT_RESULT_COUNT = 5

_MARKUP = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")
_LIVE_TOPIC = re.compile(
    r"\b(latest|today|todays|news|current|currently|price|prices|weather|score|"
    r"scores|recent|recently|stock|stocks|this week|right now|who won)\b",
    re.IGNORECASE,
)
_SEARCH_PREFIX = re.compile(r"^\s*search(\s+for)?\s*[:,-]?\s*", re.IGNORECASE)


class WebSearchError(AuroraError):
    code = "web_search_error"


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearch(Protocol):
    async def search(
        self, query: str, count: int = DEFAULT_RESULT_COUNT
    ) -> list[SearchResult]: ...


def _clean(text: str) -> str:
    return _SPACES.sub(" ", _MARKUP.sub("", text)).strip()


def parse_results(
    payload: dict[str, Any], count: int = DEFAULT_RESULT_COUNT
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for item in payload.get("results") or []:
        title, url = item.get("title"), item.get("url")
        if not title or not url:
            continue
        results.append(
            SearchResult(
                title=_clean(title),
                url=url,
                snippet=_clean(item.get("content") or ""),
            )
        )
    return results[:count]


def format_results(results: list[SearchResult]) -> str:
    if not results:
        return "The web search found no results for this question."
    return "\n\n".join(
        f"{number}. {item.title} ({item.url})\n{item.snippet}"
        for number, item in enumerate(results, start=1)
    )


def needs_web_search(message: str) -> bool:
    if _SEARCH_PREFIX.match(message):
        return True
    return _LIVE_TOPIC.search(message) is not None


def search_query(message: str) -> str:
    stripped = _SEARCH_PREFIX.sub("", message, count=1).strip()
    return stripped or message.strip()


class TavilySearch:
    def __init__(
        self,
        api_key: str,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._factory = client_factory or (lambda: httpx.AsyncClient(timeout=timeout))

    async def search(
        self, query: str, count: int = DEFAULT_RESULT_COUNT
    ) -> list[SearchResult]:
        client = self._factory()
        try:
            response = await client.post(
                TAVILY_ENDPOINT,
                json={"query": query, "max_results": count, "search_depth": "basic"},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.HTTPError as exc:
            raise WebSearchError("The web search could not be reached.") from exc
        finally:
            await client.aclose()
        if response.status_code != 200:
            raise WebSearchError(
                f"The web search failed with status {response.status_code}."
            )
        return parse_results(response.json(), count)
