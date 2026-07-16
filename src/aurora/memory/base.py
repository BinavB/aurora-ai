"""The memory abstraction every backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from aurora.core.types import Message


class BaseMemory(ABC):
    """Abstract per-session conversation store."""

    @abstractmethod
    async def append(self, session_id: str, message: Message) -> None:
        """Append a message to a session's history."""
        raise NotImplementedError

    @abstractmethod
    async def history(self, session_id: str) -> list[Message]:
        """Return a copy of a session's message history (oldest first)."""
        raise NotImplementedError

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """Remove all history for a session."""
        raise NotImplementedError

    async def extend(self, session_id: str, messages: list[Message]) -> None:
        """Append several messages in order."""
        for message in messages:
            await self.append(session_id, message)
