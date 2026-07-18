"""Request bodies for the API. Responses reuse the service result models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KeysBody(BaseModel):
    """Provider API keys to apply at runtime (``{provider: key}``)."""

    keys: dict[str, str] = Field(default_factory=dict)


class CollaborateBody(BaseModel):
    """Request body for a structured multi-agent (team) run."""

    task: str = Field(min_length=1)
    mode: str = "chat"  # chat | plan | review | implement | summarize | explain
    effort: str = "balanced"  # fast | balanced | max


class ChatBody(BaseModel):
    """Request body for a chat turn."""

    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    offline: bool = False
    prefer_provider: str | None = None
    prefer_model: str | None = None
    images: list[str] = Field(default_factory=list)


class PlanBody(BaseModel):
    """Request body for a planning request."""

    task: str = Field(min_length=1)
    offline: bool = False
    prefer_provider: str | None = None
    prefer_model: str | None = None


class ReviewBody(BaseModel):
    """Request body for a review request."""

    code: str = Field(min_length=1)
    focus: str = "correctness, clarity, and bugs"
    offline: bool = False
    prefer_provider: str | None = None
    prefer_model: str | None = None


class ImplementBody(BaseModel):
    """Request body for an implementation request.

    ``target_path`` is relative to the server's configured workspace; the
    filesystem tools additionally sandbox it. ``approve`` gates writing.
    """

    instruction: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    approve: bool = False
    offline: bool = False
    prefer_provider: str | None = None
    prefer_model: str | None = None


class AgentBody(BaseModel):
    """Request body for an autonomous agent run.

    The agent writes files and runs commands in the server workspace, so the
    endpoint is only mounted in a trusted context (see ``enable_agent``).
    """

    task: str = Field(min_length=1)
    max_steps: int = Field(default=12, ge=1, le=40)
    offline: bool = False
    prefer_provider: str | None = None
    prefer_model: str | None = None
