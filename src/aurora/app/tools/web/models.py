"""Typed input/output models for the web tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FetchUrlInput(BaseModel):
    """Input for fetching a single web page."""

    url: str = Field(min_length=1)
    max_chars: int = Field(default=8000, gt=0, le=50000)


class FetchUrlOutput(BaseModel):
    """The readable text of a fetched page."""

    url: str
    status: int
    title: str
    text: str
    truncated: bool
