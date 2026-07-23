"""Value objects for the enforcement layer (guards).

These turn AURORA's prompt-level principles into checkable data: a guard
verdict, the evidence an agent accumulated, and the completion check that gates
success. They depend only on pydantic — no agent or provider imports — so any
layer can consume them without a cycle.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GuardLevel(StrEnum):
    """Severity of a hallucination-guard verdict."""

    SAFE = "SAFE"
    WARNING = "WARNING"
    BLOCK = "BLOCK"


class GuardVerdict(BaseModel):
    """The guard's judgement of an agent's answer against its evidence."""

    level: GuardLevel
    reasons: list[str] = Field(default_factory=list)


class AgentEvidence(BaseModel):
    """What an agent actually did — the basis for claiming completion.

    Attributes:
        task_id: Short identifier for the run.
        verified_files: Files the agent read or wrote (i.e. actually touched).
        commands_executed: Shell/test commands the agent ran.
        tool_results: Compact ``tool:ok|fail`` markers for each tool call.
        assumptions: Assumptions the agent declared it was making.
        confidence_score: The agent's self-reported confidence (0-100).
    """

    task_id: str = ""
    verified_files: list[str] = Field(default_factory=list)
    commands_executed: list[str] = Field(default_factory=list)
    tool_results: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence_score: int = 0


class CompletionCheck(BaseModel):
    """The gate applied before an autonomous run may report success."""

    implemented: bool
    inspected: bool
    tested: bool
    errors_checked: bool
    assumptions_documented: bool
    passed: bool
    reasons: list[str] = Field(default_factory=list)
