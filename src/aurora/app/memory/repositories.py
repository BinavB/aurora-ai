"""SQLite implementations of the memory repositories."""

from __future__ import annotations

from aurora.app.core.types import Role
from aurora.app.database.engine import Database
from aurora.app.memory.interfaces import (
    ConversationRepository,
    KeyValueRepository,
    RecordRepository,
)
from aurora.app.memory.models import Record, RecordKind, StoredMessage


class SqliteConversationRepository(ConversationRepository):
    """Conversation history stored in the ``conversations`` table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def add(self, message: StoredMessage) -> None:
        await self._db.execute(
            "INSERT INTO conversations (session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (message.session_id, message.role.value, message.content, message.created_at),
        )

    async def history(self, session_id: str) -> list[StoredMessage]:
        rows = await self._db.query(
            "SELECT session_id, role, content, created_at FROM conversations "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        )
        return [
            StoredMessage(
                session_id=row["session_id"],
                role=Role(row["role"]),
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def clear(self, session_id: str) -> None:
        await self._db.execute(
            "DELETE FROM conversations WHERE session_id = ?", (session_id,)
        )


class SqliteRecordRepository(RecordRepository):
    """Knowledge records stored in the ``records`` table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def add(self, record: Record) -> int:
        return await self._db.execute(
            "INSERT INTO records (kind, title, body, created_at) VALUES (?, ?, ?, ?)",
            (record.kind.value, record.title, record.body, record.created_at),
        )

    async def list(self, kind: RecordKind | None = None) -> list[Record]:
        if kind is None:
            rows = await self._db.query(
                "SELECT id, kind, title, body, created_at FROM records "
                "ORDER BY id DESC"
            )
        else:
            rows = await self._db.query(
                "SELECT id, kind, title, body, created_at FROM records "
                "WHERE kind = ? ORDER BY id DESC",
                (kind.value,),
            )
        return [
            Record(
                id=row["id"],
                kind=RecordKind(row["kind"]),
                title=row["title"],
                body=row["body"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


class SqliteKeyValueRepository(KeyValueRepository):
    """Namespaced key/value pairs stored in the ``kv`` table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def set(self, namespace: str, key: str, value: str) -> None:
        await self._db.execute(
            "INSERT INTO kv (namespace, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT (namespace, key) DO UPDATE SET value = excluded.value",
            (namespace, key, value),
        )

    async def get(self, namespace: str, key: str) -> str | None:
        rows = await self._db.query(
            "SELECT value FROM kv WHERE namespace = ? AND key = ?", (namespace, key)
        )
        return rows[0]["value"] if rows else None

    async def items(self, namespace: str) -> dict[str, str]:
        rows = await self._db.query(
            "SELECT key, value FROM kv WHERE namespace = ? ORDER BY key", (namespace,)
        )
        return {row["key"]: row["value"] for row in rows}

    async def delete(self, namespace: str, key: str) -> None:
        await self._db.execute(
            "DELETE FROM kv WHERE namespace = ? AND key = ?", (namespace, key)
        )
