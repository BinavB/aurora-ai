"""Ollama local provider."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from aurora.app.core.exceptions import ProviderResponseError
from aurora.app.core.types import ChatRequest, ChatResponse, Usage
from aurora.app.providers.base import BaseProvider
from aurora.app.providers.registry import register_provider


@register_provider
class OllamaProvider(BaseProvider):
    """Adapter for the Ollama ``/api/chat`` endpoint (non-streaming)."""

    name = "ollama"

    def _payload(self, request: ChatRequest) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": request.temperature}
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        return {
            "model": request.model,
            "messages": [m.model_dump(mode="json") for m in request.messages],
            "stream": False,
            "options": options,
        }

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        response = await self.client.post("/api/chat", json=self._payload(request))
        response.raise_for_status()
        return self._parse(response.json())

    async def _stream(self, request: ChatRequest) -> AsyncIterator[str]:
        payload = {**self._payload(request), "stream": True}
        async with self.client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                delta = self._stream_delta(line)
                if delta:
                    yield delta

    @staticmethod
    def _stream_delta(line: str) -> str | None:
        """Extract content from one Ollama newline-delimited JSON chunk."""
        line = line.strip()
        if not line:
            return None
        try:
            message = json.loads(line).get("message") or {}
        except json.JSONDecodeError:
            return None
        content = message.get("content")
        return content if isinstance(content, str) and content else None

    def _parse(self, data: dict[str, Any]) -> ChatResponse:
        try:
            content = data["message"]["content"]
            return ChatResponse(
                model=str(data.get("model", "")),
                content=content,
                usage=Usage(
                    prompt_tokens=data.get("prompt_eval_count", 0),
                    completion_tokens=data.get("eval_count", 0),
                ),
            )
        except (KeyError, TypeError) as exc:
            raise ProviderResponseError(
                f"{self.name} returned an unexpected response shape",
                details={"provider": self.name},
            ) from exc
