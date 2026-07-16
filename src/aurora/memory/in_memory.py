"""Process-local conversation memory."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from aurora.core.types import Message
from aurora.memory.base import BaseMemory


class InMemoryMemory(BaseMemory):
    """Keeps per-session history in a dictionary, guarded by a lock.

    Suitable for a single process; swap for a persistent backend in production
    deployments that span processes.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[Message]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def append(self, session_id: str, message: Message) -> None:
        async with self._lock:
            self._store[session_id].append(message)

    async def history(self, session_id: str) -> list[Message]:
        async with self._lock:
            return list(self._store.get(session_id, ()))

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            self._store.pop(session_id, None)
