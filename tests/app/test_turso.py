import json
import sqlite3

import httpx
import pytest

from aurora.app.database import build_database
from aurora.app.database.engine import Database
from aurora.app.database.turso import TursoDatabase, _decode, _encode
from aurora.app.memory.store import MemoryStore


def fake_turso(store: sqlite3.Connection, seen_auth: list[str]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("Authorization", ""))
        body = json.loads(request.content)
        statement = body["requests"][0]["stmt"]
        args = [_decode(arg) for arg in statement["args"]]
        cursor = store.execute(statement["sql"], args)
        store.commit()
        cols = [{"name": c[0]} for c in cursor.description or []]
        rows = [[_encode(v) for v in row] for row in cursor.fetchall()]
        result = {
            "type": "ok",
            "response": {
                "type": "execute",
                "result": {
                    "cols": cols,
                    "rows": rows,
                    "last_insert_rowid": str(cursor.lastrowid or 0),
                },
            },
        }
        return httpx.Response(200, json={"results": [result, {"type": "ok"}]})

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
async def test_turso_round_trip_matches_the_local_database_interface():
    seen: list[str] = []
    backend = sqlite3.connect(":memory:", check_same_thread=False)
    db = TursoDatabase(
        "libsql://example.turso.io", "secret-token", transport=fake_turso(backend, seen)
    )
    await db.connect()

    memory = MemoryStore(db)
    await memory.add_message("chat-1", "user", "hello")
    await memory.add_message("chat-1", "assistant", "hi there")

    history = await memory.conversation("chat-1")
    assert [message.content for message in history] == ["hello", "hi there"]
    assert all(auth == "Bearer secret-token" for auth in seen)
    await db.close()


@pytest.mark.asyncio
async def test_turso_rows_can_be_read_by_column_name_and_nulls_survive():
    backend = sqlite3.connect(":memory:", check_same_thread=False)
    db = TursoDatabase("https://example.turso.io", "", transport=fake_turso(backend, []))
    await db.connect()

    await db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, label TEXT)")
    await db.execute("INSERT INTO t (label) VALUES (?)", [None])
    rows = await db.query("SELECT id, label FROM t")
    assert rows == [{"id": 1, "label": None}]
    await db.close()


def test_build_database_uses_turso_only_when_its_url_is_set(tmp_path):
    local = build_database(str(tmp_path / "aurora.db"))
    assert isinstance(local, Database)

    remote = build_database(
        str(tmp_path / "aurora.db"), "libsql://example.turso.io", "token"
    )
    assert isinstance(remote, TursoDatabase)


def test_libsql_urls_are_sent_over_https():
    db = TursoDatabase("libsql://example.turso.io/", "token")
    assert db._endpoint == "https://example.turso.io/v2/pipeline"
