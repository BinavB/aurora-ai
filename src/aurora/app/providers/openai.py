"""OpenAI chat completions provider."""

from __future__ import annotations

from typing import Any

from aurora.app.core.exceptions import ProviderResponseError
from aurora.app.core.types import ChatRequest, ChatResponse, Usage
from aurora.app.providers.base import BaseProvider
from aurora.app.providers.registry import register_provider


@register_provider
class OpenAIProvider(BaseProvider):
    """Adapter for the OpenAI ``/chat/completions`` API."""

    name = "openai"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"
        return headers

    def _payload(self, request: ChatRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [
            {"role": m.role.value, "content": m.content} for m in request.messages
        ]
        # Attach images to the final user turn (OpenAI-style multimodal content).
        if request.images:
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["content"] = [{"type": "text", "text": msg["content"]}] + [
                        {"type": "image_url", "image_url": {"url": img}}
                        for img in request.images
                    ]
                    break
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        return payload

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        response = await self.client.post(
            "/chat/completions", headers=self._headers(), json=self._payload(request)
        )
        response.raise_for_status()
        return self._parse(response.json())

    def _parse(self, data: dict[str, Any]) -> ChatResponse:
        try:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            return ChatResponse(
                model=str(data.get("model", "")),
                content=content,
                usage=Usage(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                ),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(
                f"{self.name} returned an unexpected response shape",
                details={"provider": self.name},
            ) from exc
