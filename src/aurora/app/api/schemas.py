"""Request bodies for the API. Responses reuse the service result models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatBody(BaseModel):
    """Request body for a chat turn."""

    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    offline: bool = False
    prefer_provider: str | None = None
    prefer_model: str | None = None


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
