"""Selection of a memory backend from configuration.

Keeping backend choice here means the API and other callers depend only on the
:class:`BaseMemory` abstraction, never on a concrete backend.
"""

from __future__ import annotations

import os

from aurora.core.errors import ConfigurationError
from aurora.memory.base import BaseMemory
from aurora.memory.file import FileMemory
from aurora.memory.in_memory import InMemoryMemory


def build_memory(kind: str = "memory", path: str | None = None) -> BaseMemory:
    """Build a memory backend by name.

    ``memory`` → in-process; ``file`` → JSON-Lines under ``path`` (default
    ``./.aurora/memory``).
    """
    if kind == "memory":
        return InMemoryMemory()
    if kind == "file":
        return FileMemory(path or os.path.join(os.getcwd(), ".aurora", "memory"))
    raise ConfigurationError(
        f"Unknown memory backend '{kind}'. Known: memory, file"
    )


def build_memory_from_env(env: dict[str, str] | None = None) -> BaseMemory:
    """Build a memory backend from ``AURORA_MEMORY`` / ``AURORA_MEMORY_DIR``."""
    source = os.environ if env is None else env
    return build_memory(
        kind=source.get("AURORA_MEMORY", "memory"),
        path=source.get("AURORA_MEMORY_DIR"),
    )
