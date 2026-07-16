"""Coder agent: generate the full contents for a target file.

The coder only *proposes* content; writing it to disk is the executor's job
(through the filesystem tools), keeping generation and side effects separate.
"""

from __future__ import annotations

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.llm import complete, strip_code_fences, system, user
from aurora.app.agents.models import CoderInput, CoderOutput
from aurora.app.providers.interface import LLMProvider

_SYSTEM = (
    "You are an expert software engineer. Produce production-ready code. "
    "Respond with ONLY the complete file contents, no explanation."
)


class CoderAgent(BaseAgent[CoderInput, CoderOutput]):
    """Generate the complete contents of a single file."""

    name = "coder"

    def __init__(self, provider: LLMProvider, model: str) -> None:
        self._provider = provider
        self._model = model

    async def run(self, request: CoderInput) -> CoderOutput:
        messages = [
            system(_SYSTEM),
            *request.context_messages,
            user(
                f"{request.instruction}\n\n"
                f"Respond with the complete contents of {request.target_path}."
            ),
        ]
        text = await complete(self._provider, self._model, messages)
        return CoderOutput(path=request.target_path, content=strip_code_fences(text))
