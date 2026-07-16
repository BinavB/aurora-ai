"""Default prompt builder: assemble chunks into provider-ready messages."""

from __future__ import annotations

from aurora.app.context.interfaces import PromptBuilder
from aurora.app.context.models import BuiltContext, ContextChunk, ContextRequest
from aurora.app.context.tokens import estimate_messages
from aurora.app.core.types import Message, Role

_DEFAULT_SYSTEM = "You are AURORA, an AI software engineering assistant."


class MessagePromptBuilder(PromptBuilder):
    """Build a system prompt, a context block, and the user query."""

    def build(
        self, request: ContextRequest, chunks: list[ContextChunk], truncated: bool
    ) -> BuiltContext:
        messages = [
            Message(role=Role.SYSTEM, content=request.system_prompt or _DEFAULT_SYSTEM)
        ]
        if chunks:
            body = "\n\n".join(chunk.text for chunk in chunks)
            messages.append(
                Message(role=Role.SYSTEM, content=f"Relevant project context:\n{body}")
            )
        messages.append(Message(role=Role.USER, content=request.query))
        return BuiltContext(
            messages=messages,
            token_estimate=estimate_messages(messages),
            files_used=[chunk.path for chunk in chunks],
            truncated=truncated,
        )
