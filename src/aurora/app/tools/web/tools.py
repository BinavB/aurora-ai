"""Web tools: fetch and read public web pages.

``fetch_url`` lets an agent read documentation or references. It is guarded
against SSRF — only ``http``/``https`` are allowed and the host must resolve to
a public address (blocking loopback, private ranges, and cloud metadata
endpoints). HTML is reduced to readable text; no scripts are executed.
"""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from aurora.app.core.exceptions import ToolError
from aurora.app.tools.base import BaseTool
from aurora.app.tools.models import Permission, ToolMetadata
from aurora.app.tools.web.models import FetchUrlInput, FetchUrlOutput

ClientFactory = Callable[[], httpx.AsyncClient]

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_SCRIPT_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_INLINE_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n\s*")


class FetchUrlTool(BaseTool):
    """Fetch a public web page and return its readable text."""

    metadata = ToolMetadata(
        name="fetch_url",
        description="Fetch a public web page (http/https) and return its readable text.",
        category="web",
        permissions=frozenset({Permission.NETWORK}),
    )
    input_model = FetchUrlInput
    output_model = FetchUrlOutput

    def __init__(
        self, client_factory: ClientFactory | None = None, timeout: float = 15.0
    ) -> None:
        self._factory = client_factory
        # An injected client is a trusted test/transport seam: skip DNS checks.
        self._trusted = client_factory is not None
        self._timeout = timeout
        super().__init__()

    async def execute(self, payload: FetchUrlInput) -> FetchUrlOutput:
        parsed = urlparse(payload.url)
        if parsed.scheme not in ("http", "https"):
            raise ToolError("Only http and https URLs are supported")
        if not parsed.hostname:
            raise ToolError("URL has no host")
        if not self._trusted:
            self._assert_public(parsed.hostname)
        try:
            client = (
                self._factory()
                if self._factory
                else httpx.AsyncClient(timeout=self._timeout, follow_redirects=True)
            )
            async with client:
                response = await client.get(payload.url)
        except httpx.HTTPError as exc:
            raise ToolError(f"Could not fetch URL ({type(exc).__name__})") from exc

        title, text = self._extract(response.text)
        return FetchUrlOutput(
            url=str(response.url),
            status=response.status_code,
            title=title,
            text=text[: payload.max_chars],
            truncated=len(text) > payload.max_chars,
        )

    @staticmethod
    def _assert_public(host: str) -> None:
        """Reject hosts that resolve to loopback/private/reserved addresses."""
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError as exc:
            raise ToolError(f"Could not resolve host '{host}'") from exc
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or not ip.is_global
            ):
                raise ToolError("Refusing to fetch a non-public address")

    @staticmethod
    def _extract(body: str) -> tuple[str, str]:
        match = _TITLE.search(body)
        title = html.unescape(_TAG.sub("", match.group(1))).strip() if match else ""
        stripped = _SCRIPT_STYLE.sub(" ", body)
        text = html.unescape(_TAG.sub(" ", stripped))
        text = _INLINE_WS.sub(" ", text)
        text = _BLANK_LINES.sub("\n\n", text).strip()
        return title, text
