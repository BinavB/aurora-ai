"""Memory layer: provider-independent persistence (SQLite first).

Stores conversation history, knowledge records (decisions, fixes, issues), and
namespaced metadata/preferences behind repository interfaces, so the backend is
replaceable (e.g. a vector database later) without affecting callers.
"""

from aurora.app.memory.interfaces import (
    ConversationRepository,
    KeyValueRepository,
    RecordRepository,
)
from aurora.app.memory.models import Record, RecordKind, StoredMessage
from aurora.app.memory.store import (
    NS_PREFERENCES,
    NS_PROJECT,
    NS_STYLE,
    MemoryStore,
)

__all__ = [
    "ConversationRepository",
    "KeyValueRepository",
    "RecordRepository",
    "Record",
    "RecordKind",
    "StoredMessage",
    "MemoryStore",
    "NS_PROJECT",
    "NS_PREFERENCES",
    "NS_STYLE",
]
