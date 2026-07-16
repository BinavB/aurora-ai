"""Shared, provider-agnostic domain types.

These types form the neutral vocabulary spoken by every provider. Providers
translate to and from their vendor-specific wire formats; the rest of the
platform only ever sees these models.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Author of a chat message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """A single chat message."""

    role: Role
    content: str


class ChatRequest(BaseModel):
    """A provider-agnostic chat completion request."""

    model: str
    messages: list[Message] = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)


class Usage(BaseModel):
    """Token accounting for a completion, when reported by the provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ChatResponse(BaseModel):
    """A provider-agnostic chat completion response."""

    model: str
    content: str
    usage: Usage = Field(default_factory=Usage)
