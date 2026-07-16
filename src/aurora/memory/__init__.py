"""Memory layer: conversation history behind a single abstraction.

Implementations store and retrieve per-session message history. The default
:class:`~aurora.memory.in_memory.InMemoryMemory` keeps history in process; other
backends (files, databases) can be added without touching callers.
"""

from aurora.memory.base import BaseMemory
from aurora.memory.factory import build_memory, build_memory_from_env
from aurora.memory.file import FileMemory
from aurora.memory.in_memory import InMemoryMemory

__all__ = [
    "BaseMemory",
    "FileMemory",
    "InMemoryMemory",
    "build_memory",
    "build_memory_from_env",
]
