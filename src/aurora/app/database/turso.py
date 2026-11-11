"""Turso (hosted libSQL) persistence, used when ``TURSO_DATABASE_URL`` is set.

Talks to Turso's HTTP pipeline API with ``httpx`` (already a dependency), so no
new package is needed. Exposes the same ``connect``/``execute``/``query``/
``close`` surface as the local SQLite ``Database``, and rows can be read by
column name just like ``sqlite3.Row``.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any

import httpx

from aurora.app.core.exceptions import ConfigurationError
from aurora.app.database.schema import SCHEMA

Params = Sequence[Any]


def _https_base(url: str) -> str:
    base = "https://" + url[len("libsql://") :] if url.startswith("libsql://") else url
    return base.rstrip("/")


def _encode(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, bytes):
        return {"type": "blob", "base64": base64.b64encode(value).decode("ascii")}
    return {"type": "text", "value": str(value)}


def _decode(cell: dict[str, Any]) -> Any:
    kind = cell.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(cell["value"])
    if kind == "float":
        return float(cell["value"])
    if kind == "blob":
        return base64.b64decode(cell["base64"])
    return cell.get("value")


class TursoDatabase:
    """A Turso database reached over HTTP."""

    def __init__(
        self, url: str, auth_token: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not url:
            raise ConfigurationError("TURSO_DATABASE_URL is empty")
        self._endpoint = f"{_https_base(url)}/v2/pipeline"
        self._headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = httpx.AsyncClient(timeout=30, transport=self._transport)
        for statement in SCHEMA:
            await self.execute(statement)

    def _require(self) -> httpx.AsyncClient:
        if self._client is None:
            raise ConfigurationError("Database is not connected; call connect() first")
        return self._client

    async def _pipeline(self, sql: str, params: Params) -> dict[str, Any]:
        client = self._require()
        body = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {"sql": sql, "args": [_encode(p) for p in params]},
                },
                {"type": "close"},
            ]
        }
        response = await client.post(self._endpoint, json=body, headers=self._headers)
        response.raise_for_status()
        result = response.json()["results"][0]
        if result.get("type") != "ok":
            raise ConfigurationError(
                f"Turso rejected the statement: {result.get('error', result)}"
            )
        return result["response"]["result"]

    async def execute(self, sql: str, params: Params = ()) -> int:
        """Execute a write statement and return the last inserted row id."""
        result = await self._pipeline(sql, params)
        return int(result.get("last_insert_rowid") or 0)

    async def query(self, sql: str, params: Params = ()) -> list[dict[str, Any]]:
        """Execute a read statement and return all rows as name-addressable mappings."""
        result = await self._pipeline(sql, params)
        names = [column["name"] for column in result.get("cols", [])]
        return [
            dict(zip(names, (_decode(cell) for cell in row), strict=True))
            for row in result.get("rows", [])
        ]

    async def close(self) -> None:
        if self._client is not None:
            client = self._client
            self._client = None
            await client.aclose()
