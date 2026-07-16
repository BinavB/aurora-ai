"""Conversation agent: multi-turn chat with persistent memory."""

from __future__ import annotations

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.models import ConversationTurn
from aurora.app.core.types import ChatRequest, ChatResponse, Message, Role
from aurora.app.memory.store import MemoryStore
from aurora.app.providers.interface import LLMProvider


class ConversationAgent(BaseAgent[ConversationTurn, ChatResponse]):
    """Run a stateful conversation, persisting turns through memory.

    On each turn the agent loads prior history from memory, prepends an
    optional system prompt, asks the provider for a reply, then persists both
    the user message and the assistant reply.
    """

    name = "conversation"

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        memory: MemoryStore,
        system_prompt: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._memory = memory
        self._system_prompt = system_prompt

    async def run(self, request: ConversationTurn) -> ChatResponse:
        history = await self._memory.conversation(request.session_id)
        messages: list[Message] = []
        if self._system_prompt:
            messages.append(Message(role=Role.SYSTEM, content=self._system_prompt))
        messages.extend(Message(role=m.role, content=m.content) for m in history)
        messages.append(Message(role=Role.USER, content=request.message))

        response = await self._provider.chat(
            ChatRequest(model=self._model, messages=messages)
        )

        await self._memory.add_message(request.session_id, Role.USER, request.message)
        await self._memory.add_message(
            request.session_id, Role.ASSISTANT, response.content
        )
        return response
