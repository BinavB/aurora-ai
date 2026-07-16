"""Anthropic Messages API provider."""

from __future__ import annotations

from aurora.core.errors import ProviderResponseError
from aurora.core.types import ChatRequest, ChatResponse, Role, Usage
from aurora.providers.base import BaseProvider
from aurora.providers.registry import register_provider

_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_MAX_TOKENS = 1024


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
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key
        return headers

    def _payload(self, request: ChatRequest) -> dict[str, object]:
        system_parts = [m.content for m in request.messages if m.role is Role.SYSTEM]
        turns = [
            {"role": m.role.value, "content": m.content}
            for m in request.messages
            if m.role is not Role.SYSTEM
        ]
        payload: dict[str, object] = {
            "model": request.model,
            "messages": turns,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or _DEFAULT_MAX_TOKENS,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return payload

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        response = await self.client.post(
            "/messages",
            headers=self._headers(),
            json=self._payload(request),
        )
        response.raise_for_status()
        return self._parse(response.json())

    def _parse(self, data: dict[str, object]) -> ChatResponse:
        try:
            blocks = data["content"]  # type: ignore[index]
            text = "".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            )
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
                f"{self.name} returned an unexpected response shape"
            ) from exc
