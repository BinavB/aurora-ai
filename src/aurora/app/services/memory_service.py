"""Memory service — the Learn stage of the agentic pipeline.

Persists each completed episode as a durable knowledge record so future runs can
recall what was attempted and whether it worked. A verified success is stored as
a FIX; a failure is stored as an ISSUE, capturing the problems found.
"""

from __future__ import annotations

from aurora.app.memory.models import RecordKind
from aurora.app.memory.store import MemoryStore
from aurora.app.services.models import (
    AgentResult,
    MemoryReceipt,
    TaskSpec,
    VerificationReport,
)

_TITLE_MAX = 80


class MemoryService:
    """Learn stage: record the episode's outcome for future recall."""

    def __init__(self, memory: MemoryStore) -> None:
        self._memory = memory

    async def learn(
        self,
        spec: TaskSpec,
        execution: AgentResult,
        verification: VerificationReport,
    ) -> MemoryReceipt:
        """Persist the outcome as a FIX (verified) or ISSUE (not verified)."""
        kind = RecordKind.FIX if verification.passed else RecordKind.ISSUE
        record_id = await self._memory.remember(
            kind, spec.objective[:_TITLE_MAX], self._render(spec, execution, verification)
        )
        return MemoryReceipt(stored=True, record_id=record_id)

    @staticmethod
    def _render(
        spec: TaskSpec, execution: AgentResult, verification: VerificationReport
    ) -> str:
        """Compose a compact, human-readable episode summary."""
        lines = [
            f"Objective: {spec.objective}",
            f"Model: {execution.provider}/{execution.model}",
            f"Completed: {execution.report.completed}",
            f"Outcome: {execution.report.answer}",
            f"Verification: {'PASS' if verification.passed else 'FAIL'} — "
            f"{verification.summary}",
        ]
        if verification.issues:
            lines.append("Issues:\n" + "\n".join(f"- {i}" for i in verification.issues))
        return "\n".join(lines)
