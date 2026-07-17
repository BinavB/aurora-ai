"""Shared, provider-agnostic domain types.

These models are the neutral vocabulary spoken across layers. Providers
translate between them and vendor wire formats; nothing above the providers
layer sees vendor-specific shapes.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from aurora.app.core.constants import DEFAULT_TEMPERATURE


class Role(StrEnum):
    """Author of a chat message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """A single chat message.

    Attributes:
        role: Who authored the message.
        content: The message text.
    """

    role: Role
    content: str


class ChatRequest(BaseModel):
    """A provider-agnostic chat completion request.

    ``images`` holds optional image attachments (base64 ``data:`` URLs or raw
    base64) for the final user turn; only vision-capable providers use them.
    """

    model: str = Field(min_length=1)
    messages: list[Message] = Field(min_length=1)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    images: list[str] = Field(default_factory=list)


class Usage(BaseModel):
    """Token accounting reported by a provider, when available."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        """Sum of prompt and completion tokens."""
        return self.prompt_tokens + self.completion_tokens


class ChatResponse(BaseModel):
    """A provider-agnostic chat completion response."""

    model: str
    content: str
    usage: Usage = Field(default_factory=Usage)
