"""Database schema (SQLite).

DDL is idempotent so :meth:`Database.connect` can apply it on every startup.
Schema changes append new statements rather than mutating existing ones.
"""

from __future__ import annotations

from typing import Final

_CONVERSATIONS: Final = """
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

_CONVERSATIONS_INDEX: Final = (
    "CREATE INDEX IF NOT EXISTS idx_conversations_session "
    "ON conversations (session_id)"
)

_RECORDS: Final = """
CREATE TABLE IF NOT EXISTS records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

_KV: Final = """
CREATE TABLE IF NOT EXISTS kv (
    namespace TEXT NOT NULL,
    key       TEXT NOT NULL,
    value     TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
)
"""

#: All DDL statements, applied in order.
SCHEMA: Final[tuple[str, ...]] = (
    _CONVERSATIONS,
    _CONVERSATIONS_INDEX,
    _RECORDS,
    _KV,
)
