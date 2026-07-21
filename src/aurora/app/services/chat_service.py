"""Chat service: coordinate a conversational turn end to end."""

from __future__ import annotations

from collections.abc import AsyncIterator

from aurora.app.agents.conversation import ConversationAgent
from aurora.app.agents.llm import system as system_msg
from aurora.app.agents.models import ConversationTurn
from aurora.app.core.exceptions import ProviderError, RouterError
from aurora.app.core.types import ChatRequest, Message, Role
from aurora.app.memory.store import MemoryStore
from aurora.app.providers.base import BaseProvider
from aurora.app.router.intent import classify_intent
from aurora.app.router.models import Capability, RoutingDecision, RoutingRequest
from aurora.app.router.router import Router
from aurora.app.services.base import RoutedService
from aurora.app.services.factory import ProviderFactory
from aurora.app.services.models import ChatReply, StreamChunk


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
        images: list[str] | None = None,
    ) -> ChatReply:
        """Handle one chat turn for a session (optionally with images)."""
        if images:
            return await self._chat_with_images(
                session_id, message, images, offline, prefer_provider, prefer_model
            )

        request = RoutingRequest(
            task=message,
            kind=classify_intent(message),
            offline=offline,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )

        async def work(decision, provider):
            agent = ConversationAgent(
                provider, decision.model, self._memory, self._system_prompt
            )
            return await agent.run(
                ConversationTurn(session_id=session_id, message=message)
            )

        decision, response = await self._attempt(request, work)
        return ChatReply(
            provider=decision.provider,
            model=decision.model,
            content=response.content,
            total_tokens=response.usage.total_tokens,
        )

    async def stream_chat(
        self,
        session_id: str,
        message: str,
        offline: bool = False,
        prefer_provider: str | None = None,
        prefer_model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream one chat turn as tokens, then persist it.

        Candidates are tried in routing order; a provider that fails *before*
        emitting its first token falls over to the next. Once tokens flow the
        stream is committed, and the full turn is saved to memory at the end.
        """
        request = RoutingRequest(
            task=message,
            kind=classify_intent(message),
            offline=offline,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        decisions = self._router.rank(request)
        if not decisions:
            raise RouterError(
                "No available model satisfies the routing constraints",
                details={"task": message},
            )
        messages = await self._history_messages(session_id, message)

        last: ProviderError | None = None
        for decision in decisions:
            provider = self._factory.create(decision.provider)
            chat_request = ChatRequest(
                model=decision.model, messages=messages, temperature=0.3
            )
            stream = provider.stream(chat_request).__aiter__()
            try:
                first: str | None = await anext(stream)
            except StopAsyncIteration:
                first = None
            except ProviderError as exc:  # failed before first token -> fail over
                last = exc
                await provider.aclose()
                continue
            async for chunk in self._drain(
                provider, session_id, message, decision, first, stream
            ):
                yield chunk
            return
        raise last or RouterError("All candidate providers failed")

    async def _drain(
        self,
        provider: BaseProvider,
        session_id: str,
        message: str,
        decision: RoutingDecision,
        first: str | None,
        stream: AsyncIterator[str],
    ) -> AsyncIterator[StreamChunk]:
        """Yield token frames from a committed stream, then persist and finish."""
        pieces: list[str] = []
        try:
            if first is not None:
                pieces.append(first)
                yield StreamChunk(type="token", content=first)
            async for delta in stream:
                pieces.append(delta)
                yield StreamChunk(type="token", content=delta)
        finally:
            await provider.aclose()
        full = "".join(pieces)
        await self._memory.add_message(session_id, Role.USER, message)
        await self._memory.add_message(session_id, Role.ASSISTANT, full)
        yield StreamChunk(
            type="done",
            provider=decision.provider,
            model=decision.model,
            content=full,
        )

    async def _history_messages(self, session_id: str, message: str) -> list[Message]:
        """Build the prompt messages: system prompt, history, then the new turn."""
        history = await self._memory.conversation(session_id)
        messages: list[Message] = []
        if self._system_prompt:
            messages.append(system_msg(self._system_prompt))
        messages.extend(Message(role=m.role, content=m.content) for m in history)
        messages.append(Message(role=Role.USER, content=message))
        return messages

    async def _chat_with_images(
        self,
        session_id: str,
        message: str,
        images: list[str],
        offline: bool,
        prefer_provider: str | None,
        prefer_model: str | None,
    ) -> ChatReply:
        """A vision turn: require a vision-capable model and pass the images."""
        messages = await self._history_messages(session_id, message)
        request = RoutingRequest(
            task=message,
            required_capabilities=frozenset({Capability.VISION}),
            offline=offline,
            prefer_provider=prefer_provider,
            prefer_model=prefer_model,
        )
        decision, text = await self._complete(request, messages, images=images)
        await self._memory.add_message(session_id, Role.USER, message)
        await self._memory.add_message(session_id, Role.ASSISTANT, text)
        return ChatReply(
            provider=decision.provider, model=decision.model, content=text, total_tokens=0
        )
