"""Reviewer agent: review code and return structured findings."""

from __future__ import annotations

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.llm import complete, lead_system, parse_list_items, user
from aurora.app.agents.models import ReviewInput, ReviewResult
from aurora.app.providers.interface import LLMProvider

_SYSTEM = (
    "You are a meticulous code reviewer. List concrete issues as bullet points, "
    "then a final line starting with 'Summary:'."
)
_SUMMARY_MARKER = "summary:"
# Markers a model might use to introduce its closing summary, in priority order.
_SUMMARY_HINTS = ("summary", "overall", "in summary", "conclusion", "verdict")


class ReviewerAgent(BaseAgent[ReviewInput, ReviewResult]):
    """Review code and extract findings plus a summary."""

    name = "reviewer"

    def __init__(
        self, provider: LLMProvider, model: str, system_prompt: str | None = None
    ) -> None:
        self._provider = provider
        self._model = model
        self._system_prompt = system_prompt

    async def run(self, request: ReviewInput) -> ReviewResult:
        messages = [
            lead_system(self._system_prompt, _SYSTEM),
            user(f"Review the following for {request.focus}:\n\n{request.code}"),
        ]
        text = await complete(self._provider, self._model, messages)
        findings = self._findings(text)
        return ReviewResult(
            summary=self._summary(text) or self._fallback_summary(findings),
            findings=findings,
        )

    @staticmethod
    def _findings(text: str) -> list[str]:
        return [
            item
            for item in parse_list_items(text)
            if not item.lower().startswith(_SUMMARY_MARKER)
        ]

    @staticmethod
    def _summary(text: str) -> str:
        """Extract the model's summary, tolerating markdown and varied phrasing."""
        lines = [ln.rstrip() for ln in text.splitlines()]
        for i, line in enumerate(lines):
            head = line.lstrip("#*->•· \t").lower()
            if not any(head.startswith(hint) for hint in _SUMMARY_HINTS):
                continue
            rest = line.split(":", 1)[1] if ":" in line else ""
            rest = rest.strip(" *_#").strip()
            if rest:
                return rest
            # "Summary:" alone on its line — take the following prose line.
            for nxt in lines[i + 1 :]:
                cleaned = nxt.strip(" *_#").strip()
                if cleaned:
                    return cleaned
        return ""

    @staticmethod
    def _fallback_summary(findings: list[str]) -> str:
        """A useful summary when the model didn't label one explicitly."""
        n = len(findings)
        if n == 0:
            return "No issues found."
        return f"{n} issue{'s' if n != 1 else ''} identified."
