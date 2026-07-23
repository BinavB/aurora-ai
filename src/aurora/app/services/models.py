"""Result models returned by services."""

from __future__ import annotations

from pydantic import BaseModel, Field

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


class StreamChunk(BaseModel):
    """One frame of a streamed chat turn.

    ``type`` is ``"token"`` for an incremental delta (``content``) or ``"done"``
    for the terminal frame, which also carries the chosen ``provider``/``model``
    and the full assembled ``content``.
    """

    type: str
    content: str = ""
    provider: str | None = None
    model: str | None = None


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


# --- agentic pipeline (Intent -> Plan -> Execute -> Verify -> Learn) --------
class TaskSpec(BaseModel):
    """The understood form of a request: the Intent stage's output."""

    objective: str
    intent: str  # a TaskKind value (chat/plan/review/implement/...)
    constraints: list[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    """The Verify stage's judgement of whether execution met the objective."""

    provider: str
    model: str
    passed: bool
    summary: str
    issues: list[str] = Field(default_factory=list)


class MemoryReceipt(BaseModel):
    """The Learn stage's record of what was persisted."""

    stored: bool
    record_id: int | None = None


class PipelineAttempt(BaseModel):
    """One execute→verify attempt within the pipeline's retry escalation."""

    strategy: str
    provider: str
    model: str
    verified: bool


class PipelineResult(BaseModel):
    """The end-to-end outcome of the agentic pipeline.

    ``status`` is ``COMPLETE`` when verification passed, else ``NEEDS_INPUT``.
    ``attempts`` records the escalation history (strategy + model + verdict).
    """

    objective: str
    intent: str
    plan: Plan
    execution: AgentResult
    verification: VerificationReport
    memory: MemoryReceipt
    status: str = "COMPLETE"
    attempts: list[PipelineAttempt] = Field(default_factory=list)
