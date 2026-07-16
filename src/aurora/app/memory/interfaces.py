"""Repository interfaces (repository pattern).

Higher layers depend on these abstractions, never on the SQLite implementation,
so the storage backend (e.g. a future vector database) is replaceable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aurora.app.memory.models import Record, RecordKind, StoredMessage


class ConversationRepository(ABC):
    """Persistence for conversation history."""

    @abstractmethod
    async def add(self, message: StoredMessage) -> None:
        """Append a message to its session."""

    @abstractmethod
    async def history(self, session_id: str) -> list[StoredMessage]:
        """Return a session's messages, oldest first."""

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """Remove all messages for a session."""


class RecordRepository(ABC):
    """Persistence for durable knowledge records."""

    @abstractmethod
    async def add(self, record: Record) -> int:
        """Persist a record and return its id."""

    @abstractmethod
    async def list(self, kind: RecordKind | None = None) -> list[Record]:
        """Return records, optionally filtered by kind, newest first."""


class KeyValueRepository(ABC):
    """Namespaced key/value persistence for metadata and preferences."""

    @abstractmethod
    async def set(self, namespace: str, key: str, value: str) -> None:
        """Upsert a value."""

    @abstractmethod
    async def get(self, namespace: str, key: str) -> str | None:
        """Return a value, or ``None`` if absent."""

    @abstractmethod
    async def items(self, namespace: str) -> dict[str, str]:
        """Return all key/value pairs in a namespace."""

    @abstractmethod
    async def delete(self, namespace: str, key: str) -> None:
        """Remove a key if present."""
