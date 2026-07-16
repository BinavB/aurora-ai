"""Ollama local provider."""

from __future__ import annotations

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
