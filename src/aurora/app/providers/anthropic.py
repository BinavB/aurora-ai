"""Anthropic Messages API provider."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Final

from aurora.app.core.exceptions import ProviderResponseError
from aurora.app.core.types import ChatRequest, ChatResponse, Role, Usage
from aurora.app.providers.base import BaseProvider
from aurora.app.providers.registry import register_provider

_ANTHROPIC_VERSION: Final[str] = "2023-06-01"
_DEFAULT_MAX_TOKENS: Final[int] = 1024


@register_provider
class AnthropicProvider(BaseProvider):
    """Adapter for the Anthropic ``/messages`` API.

    Anthropic carries the system prompt out-of-band rather than as a message,
    so system messages are hoisted into the top-level ``system`` field.
    """

    name = "anthropic"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        if self._settings.api_key:
            headers["x-api-key"] = self._settings.api_key
        return headers

    def _payload(self, request: ChatRequest) -> dict[str, Any]:
        system = [m.content for m in request.messages if m.role is Role.SYSTEM]
        turns = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
            if m.role is not Role.SYSTEM
        ]
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": turns,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or _DEFAULT_MAX_TOKENS,
        }
        if system:
            payload["system"] = "\n\n".join(system)
        return payload

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        response = await self.client.post(
            "/messages", headers=self._headers(), json=self._payload(request)
        )
        response.raise_for_status()
        return self._parse(response.json())

    async def _stream(self, request: ChatRequest) -> AsyncIterator[str]:
        payload = {**self._payload(request), "stream": True}
        async with self.client.stream(
            "POST", "/messages", headers=self._headers(), json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                delta = self._stream_delta(line)
                if delta:
                    yield delta

    @staticmethod
    def _stream_delta(line: str) -> str | None:
        """Extract text from one Anthropic ``content_block_delta`` SSE line."""
        if not line.startswith("data:"):
            return None
        data = line[5:].strip()
        if not data:
            return None
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            return None
        if event.get("type") != "content_block_delta":
            return None
        delta = event.get("delta") or {}
        text = delta.get("text")
        return (
            text if delta.get("type") == "text_delta" and isinstance(text, str) else None
        )

    def _parse(self, data: dict[str, Any]) -> ChatResponse:
        try:
            blocks = data["content"]
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            usage = data.get("usage") or {}
            return ChatResponse(
                model=str(data.get("model", "")),
                content=text,
                usage=Usage(
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                ),
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise ProviderResponseError(
                f"{self.name} returned an unexpected response shape",
                details={"provider": self.name},
            ) from exc
