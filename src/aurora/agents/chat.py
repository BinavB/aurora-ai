"""A multi-turn conversational agent."""

from __future__ import annotations

from aurora.agents.base import BaseAgent
from aurora.core.types import ChatRequest, ChatResponse, Message, Role
from aurora.memory.base import BaseMemory
from aurora.providers.base import BaseProvider


class ChatAgent(BaseAgent):
    """Runs a conversation by composing a provider with a memory backend.

    On each turn the agent loads the session history, appends the new user
    message, asks the provider for a completion, then persists both the user
    message and the assistant reply. An optional system prompt is prepended to
    every request without being stored as conversation history.
    """

    def __init__(
        self,
        provider: BaseProvider,
        memory: BaseMemory,
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> None:
        self._provider = provider
        self._memory = memory
        self._model = model
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def run(self, session_id: str, user_input: str) -> ChatResponse:
        user_message = Message(role=Role.USER, content=user_input)
        history = await self._memory.history(session_id)

        prompt: list[Message] = []
        if self._system_prompt:
            prompt.append(Message(role=Role.SYSTEM, content=self._system_prompt))
        prompt.extend(history)
        prompt.append(user_message)

        response = await self._provider.chat(
            ChatRequest(
                model=self._model,
                messages=prompt,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        )

        await self._memory.extend(
            session_id,
            [user_message, Message(role=Role.ASSISTANT, content=response.content)],
        )
        return response
