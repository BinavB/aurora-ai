"""Result models returned by services."""

from __future__ import annotations

from pydantic import BaseModel

from aurora.app.agents.models import (
    AutonomousReport,
    CoderOutput,
    ExecutionReport,
    Plan,
    ReviewResult,
)


class ChatReply(BaseModel):
    """The result of a chat turn."""

    provider: str
    model: str
    content: str
    total_tokens: int


class PlanResult(BaseModel):
    """The result of a planning request."""

    provider: str
    model: str
    plan: Plan
    context_files: list[str]


class ReviewOutcome(BaseModel):
    """The result of a review request."""

    provider: str
    model: str
    result: ReviewResult


class ImplementResult(BaseModel):
    """The result of an implementation request.

    ``executed`` is ``False`` for a dry run (no approval); when approved,
    ``report`` holds the executor's structured outcome.
    """

    provider: str
    model: str
    proposed: CoderOutput
    executed: bool
    report: ExecutionReport | None = None


class AgentResult(BaseModel):
    """The result of an autonomous agent run: transcript plus outcome."""

    provider: str
    model: str
    report: AutonomousReport
