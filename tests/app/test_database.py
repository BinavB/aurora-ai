"""Tests for the SQLite database engine."""

from __future__ import annotations

import pytest

from aurora.app.core.exceptions import ConfigurationError
from aurora.app.database import Database


async def test_execute_and_query_roundtrip() -> None:
    db = Database()
    await db.connect()
    row_id = await db.execute(
        "INSERT INTO kv (namespace, key, value) VALUES (?, ?, ?)", ("n", "k", "v")
    )
    assert row_id >= 1
    rows = await db.query("SELECT value FROM kv WHERE key = ?", ("k",))
    assert rows[0]["value"] == "v"
    await db.close()


async def test_query_before_connect_raises() -> None:
    with pytest.raises(ConfigurationError):
        await Database().query("SELECT 1")


async def test_connect_is_idempotent() -> None:
    db = Database()
    await db.connect()
    await db.connect()  # must not raise or reset
    await db.execute(
        "INSERT INTO kv (namespace, key, value) VALUES (?, ?, ?)", ("n", "k", "v")
    )
    assert len(await db.query("SELECT * FROM kv")) == 1
    await db.close()
