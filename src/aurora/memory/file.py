"""File-backed conversation memory.

Each session's history is a JSON Lines file under a root directory: one
:class:`Message` per line, appended in order. This survives process restarts
while keeping the same :class:`BaseMemory` contract as the in-process backend,
so callers are unaffected by the choice.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aurora.core.types import Message
from aurora.memory.base import BaseMemory


class FileMemory(BaseMemory):
    """Persist per-session history as JSON Lines files under ``root``.

    Session ids are mapped to filenames safely, so an id can never write
    outside the root (including via separators or ``..``).
    """

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _path(self, session_id: str) -> Path:
        if not session_id:
            raise ValueError("session_id must be non-empty")
        # Keep only safe characters; everything else becomes an underscore.
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self._root / f"{safe}.jsonl"

    async def append(self, session_id: str, message: Message) -> None:
        path = self._path(session_id)
        line = message.model_dump_json() + "\n"
        async with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    async def history(self, session_id: str) -> list[Message]:
        path = self._path(session_id)
        async with self._lock:
            if not path.exists():
                return []
            lines = path.read_text(encoding="utf-8").splitlines()
        return [Message.model_validate(json.loads(line)) for line in lines if line]

    async def clear(self, session_id: str) -> None:
        path = self._path(session_id)
        async with self._lock:
            path.unlink(missing_ok=True)
