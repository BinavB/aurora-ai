"""Async SQLite engine.

Wraps the stdlib ``sqlite3`` module. Calls run in a worker thread via
``asyncio.to_thread`` so they never block the event loop, and a single
connection is serialized behind a lock to keep access safe.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Sequence
from typing import Any

from aurora.app.core.exceptions import ConfigurationError
from aurora.app.core.logging import get_logger
from aurora.app.database.schema import SCHEMA

_logger = get_logger("database")

Params = Sequence[Any]


class Database:
    """A serialized, async-friendly SQLite connection."""

    def __init__(self, path: str = ":memory:") -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Open the connection (if needed) and apply the schema."""
        if self._conn is not None:
            return
        self._conn = await asyncio.to_thread(self._open)
        await self._apply_schema()
        _logger.info("database_connected", extra={"path": self._path})

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _require(self) -> sqlite3.Connection:
        if self._conn is None:
            raise ConfigurationError("Database is not connected; call connect() first")
        return self._conn

    async def _apply_schema(self) -> None:
        conn = self._require()

        def run() -> None:
            for statement in SCHEMA:
                conn.execute(statement)
            conn.commit()

        async with self._lock:
            await asyncio.to_thread(run)

    async def execute(self, sql: str, params: Params = ()) -> int:
        """Execute a write statement and return the last inserted row id."""
        conn = self._require()

        def run() -> int:
            cursor = conn.execute(sql, params)
            conn.commit()
            return int(cursor.lastrowid or 0)

        async with self._lock:
            return await asyncio.to_thread(run)

    async def query(self, sql: str, params: Params = ()) -> list[sqlite3.Row]:
        """Execute a read statement and return all rows."""
        conn = self._require()

        def run() -> list[sqlite3.Row]:
            return conn.execute(sql, params).fetchall()

        async with self._lock:
            return await asyncio.to_thread(run)

    async def close(self) -> None:
        """Close the connection if open."""
        if self._conn is not None:
            conn = self._conn
            self._conn = None
            await asyncio.to_thread(conn.close)
