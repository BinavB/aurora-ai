"""Reviewer agent: review code and return structured findings."""

from __future__ import annotations

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.llm import complete, parse_list_items, system, user
from aurora.app.agents.models import ReviewInput, ReviewResult
from aurora.app.providers.interface import LLMProvider

_SYSTEM = (
    "You are a meticulous code reviewer. List concrete issues as bullet points, "
    "then a final line starting with 'Summary:'."
)
_SUMMARY_MARKER = "summary:"


class ReviewerAgent(BaseAgent[ReviewInput, ReviewResult]):
    """Review code and extract findings plus a summary."""

    name = "reviewer"

    def __init__(self, provider: LLMProvider, model: str) -> None:
        self._provider = provider
        self._model = model

    async def run(self, request: ReviewInput) -> ReviewResult:
        messages = [
            system(_SYSTEM),
            user(f"Review the following for {request.focus}:\n\n{request.code}"),
        ]
        text = await complete(self._provider, self._model, messages)
        return ReviewResult(summary=self._summary(text), findings=self._findings(text))

    @staticmethod
    def _findings(text: str) -> list[str]:
        return [
            item
            for item in parse_list_items(text)
            if not item.lower().startswith(_SUMMARY_MARKER)
        ]

    @staticmethod
    def _summary(text: str) -> str:
        for line in text.splitlines():
            if line.strip().lower().startswith(_SUMMARY_MARKER):
                return line.split(":", 1)[1].strip()
        return "No summary provided."
