"""Task service — the Intent stage of the agentic pipeline.

Turns a raw user request into a structured :class:`TaskSpec`: the objective plus
a classified intent. This is deliberately deterministic (no LLM call) so the
pipeline's entry point is fast and predictable; richer intent/constraint
extraction can replace it behind the same method later.
"""

from __future__ import annotations

from aurora.app.router.intent import classify_intent
from aurora.app.services.models import TaskSpec


class TaskService:
    """Intent stage: understand what the user is actually asking for."""

    def understand(self, request: str) -> TaskSpec:
        """Distill a raw request into an objective and a classified intent."""
        objective = request.strip()
        if not objective:
            raise ValueError("request must not be empty")
        return TaskSpec(objective=objective, intent=classify_intent(objective).value)
