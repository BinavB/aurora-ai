"""Domain models for persisted memory."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from aurora.app.core.types import Role


class RecordKind(StrEnum):
    """The category of a knowledge record."""

    DECISION = "decision"
    FIX = "fix"
    ISSUE = "issue"
    NOTE = "note"


class StoredMessage(BaseModel):
    """A conversation message as persisted.

    Attributes:
        session_id: Conversation this message belongs to.
        role: Author of the message.
        content: Message text.
        created_at: ISO-8601 UTC timestamp.
    """

    session_id: str
    role: Role
    content: str
    created_at: str


class Record(BaseModel):
    """A durable knowledge record (decision, fix, issue, or note).

    Attributes:
        kind: The record category.
        title: Short summary.
        body: Full detail.
        created_at: ISO-8601 UTC timestamp.
        id: Database id (``None`` until persisted).
    """

    kind: RecordKind
    title: str
    body: str
    created_at: str
    id: int | None = None
