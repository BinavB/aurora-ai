"""Chat service: coordinate a conversational turn end to end."""

from __future__ import annotations

from aurora.app.agents.conversation import ConversationAgent
from aurora.app.agents.models import ConversationTurn
from aurora.app.memory.store import MemoryStore
from aurora.app.router.models import RoutingRequest
from aurora.app.router.router import Router
from aurora.app.services.base import RoutedService
from aurora.app.services.factory import ProviderFactory
from aurora.app.services.models import ChatReply


class ChatService(RoutedService):
    """Route a message, run the conversation agent, and persist the turn."""

    def __init__(
        self,
        router: Router,
        factory: ProviderFactory,
        memory: MemoryStore,
        system_prompt: str | None = None,
    ) -> None:
        super().__init__(router, factory)
        self._memory = memory
        self._system_prompt = system_prompt

    async def chat(
        self,
        session_id: str,
        message: str,
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> ChatReply:
        """Handle one chat turn for a session."""
        request = RoutingRequest(
            task=message,
            offline=offline,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        async with self._routed(request) as (decision, provider):
            agent = ConversationAgent(
                provider, decision.model, self._memory, self._system_prompt
            )
            response = await agent.run(
                ConversationTurn(session_id=session_id, message=message)
            )
        return ChatReply(
            provider=decision.provider,
            model=decision.model,
            content=response.content,
            total_tokens=response.usage.total_tokens,
        )
