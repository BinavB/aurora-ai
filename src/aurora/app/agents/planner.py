"""Planner agent: turn a task into an ordered plan."""

from __future__ import annotations

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.llm import complete, parse_list_items, system, user
from aurora.app.agents.models import Plan, PlannerInput, PlanStep
from aurora.app.providers.interface import LLMProvider

_SYSTEM = (
    "You are a senior software planner. Given a task, respond with a concise, "
    "ordered, numbered list of concrete implementation steps. No prose."
)


class PlannerAgent(BaseAgent[PlannerInput, Plan]):
    """Produce an implementation plan for a task."""

    name = "planner"

    def __init__(self, provider: LLMProvider, model: str) -> None:
        self._provider = provider
        self._model = model

    async def run(self, request: PlannerInput) -> Plan:
        messages = [
            system(_SYSTEM),
            *request.context_messages,
            user(f"Task:\n{request.task}\n\nReturn the numbered steps."),
        ]
        text = await complete(self._provider, self._model, messages)
        steps = [
            PlanStep(index=i, description=item)
            for i, item in enumerate(parse_list_items(text), start=1)
        ]
        return Plan(task=request.task, steps=steps)
