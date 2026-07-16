"""The provider-independent memory facade.

``MemoryStore`` composes the repositories into one high-level API for the rest
of the platform. It knows nothing about any LLM provider — it only persists and
recalls data.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aurora.app.core.types import Role
from aurora.app.database.engine import Database
from aurora.app.memory.models import Record, RecordKind, StoredMessage
from aurora.app.memory.repositories import (
    SqliteConversationRepository,
    SqliteKeyValueRepository,
    SqliteRecordRepository,
)

# Well-known key/value namespaces.
NS_PROJECT = "project"
NS_PREFERENCES = "preferences"
NS_STYLE = "style"

_KEY_CURRENT_MILESTONE = "current_milestone"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class MemoryStore:
    """High-level, provider-independent persistence facade."""

    def __init__(self, db: Database, clock: Callable[[], str] = _utc_now_iso) -> None:
        self._db = db
        self._clock = clock
        self.conversations = SqliteConversationRepository(db)
        self.records = SqliteRecordRepository(db)
        self.kv = SqliteKeyValueRepository(db)

    async def open(self) -> None:
        """Connect the underlying database and ensure the schema exists."""
        await self._db.connect()

    async def close(self) -> None:
        """Close the underlying database."""
        await self._db.close()

    # --- conversation history --------------------------------------------

    async def add_message(self, session_id: str, role: Role, content: str) -> None:
        """Persist one conversation message with a UTC timestamp."""
        await self.conversations.add(
            StoredMessage(
                session_id=session_id,
                role=role,
                content=content,
                created_at=self._clock(),
            )
        )

    async def conversation(self, session_id: str) -> list[StoredMessage]:
        """Return a session's message history, oldest first."""
        return await self.conversations.history(session_id)

    async def clear_conversation(self, session_id: str) -> None:
        """Delete a session's message history."""
        await self.conversations.clear(session_id)

    # --- knowledge records -----------------------------------------------

    async def remember(self, kind: RecordKind, title: str, body: str) -> int:
        """Persist a knowledge record and return its id."""
        record = Record(kind=kind, title=title, body=body, created_at=self._clock())
        return await self.records.add(record)

    async def recall(self, kind: RecordKind | None = None) -> list[Record]:
        """Return knowledge records, optionally filtered by kind, newest first."""
        return await self.records.list(kind)

    # --- project metadata / milestone ------------------------------------

    async def set_current_milestone(self, value: str) -> None:
        """Record the current milestone."""
        await self.kv.set(NS_PROJECT, _KEY_CURRENT_MILESTONE, value)

    async def current_milestone(self) -> str | None:
        """Return the current milestone, if set."""
        return await self.kv.get(NS_PROJECT, _KEY_CURRENT_MILESTONE)
