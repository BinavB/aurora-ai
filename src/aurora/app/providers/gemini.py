"""Google Gemini provider."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Final

from aurora.app.core.exceptions import ProviderResponseError
from aurora.app.core.types import ChatRequest, ChatResponse, Role, Usage
from aurora.app.providers.base import BaseProvider
from aurora.app.providers.registry import register_provider

# Gemini names the assistant role "model" and takes the system prompt in a
# dedicated field.
_ROLE_MAP: Final[dict[Role, str]] = {Role.USER: "user", Role.ASSISTANT: "model"}


def _image_part(image: str) -> dict[str, Any]:
    """Convert a data URL or raw base64 image into a Gemini inlineData part."""
    mime = "image/png"
    data = image
    if image.startswith("data:"):
        header, _, data = image.partition(",")
        mime = header[5:].split(";")[0] or mime
    return {"inlineData": {"mimeType": mime, "data": data}}


@register_provider
class GeminiProvider(BaseProvider):
    """Adapter for the Gemini ``generateContent`` API."""

    name = "gemini"

    def _params(self) -> dict[str, str]:
        return {"key": self._settings.api_key} if self._settings.api_key else {}

    def _payload(self, request: ChatRequest) -> dict[str, Any]:
        system = [m.content for m in request.messages if m.role is Role.SYSTEM]
        contents = [
            {"role": _ROLE_MAP[m.role], "parts": [{"text": m.content}]}
            for m in request.messages
            if m.role is not Role.SYSTEM
        ]
        # Attach images to the final user turn (vision).
        if request.images and contents:
            contents[-1]["parts"].extend(_image_part(img) for img in request.images)
        generation: dict[str, Any] = {"temperature": request.temperature}
        if request.max_tokens is not None:
            generation["maxOutputTokens"] = request.max_tokens
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation,
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system)}]}
        return payload

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        response = await self.client.post(
            f"/models/{request.model}:generateContent",
            params=self._params(),
            json=self._payload(request),
        )
        response.raise_for_status()
        return self._parse(response.json(), request.model)

    async def _stream(self, request: ChatRequest) -> AsyncIterator[str]:
        async with self.client.stream(
            "POST",
            f"/models/{request.model}:streamGenerateContent",
            params={**self._params(), "alt": "sse"},
            json=self._payload(request),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                delta = self._stream_delta(line)
                if delta:
                    yield delta

    @staticmethod
    def _stream_delta(line: str) -> str | None:
        """Extract text from one Gemini ``streamGenerateContent`` SSE line."""
        if not line.startswith("data:"):
            return None
        data = line[5:].strip()
        if not data:
            return None
        try:
            parts = json.loads(data)["candidates"][0]["content"]["parts"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return None
        text = "".join(p.get("text", "") for p in parts)
        return text or None

    def _parse(self, data: dict[str, Any], model: str) -> ChatResponse:
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
            usage = data.get("usageMetadata") or {}
            return ChatResponse(
                model=str(data.get("modelVersion", model)),
                content=text,
                usage=Usage(
                    prompt_tokens=usage.get("promptTokenCount", 0),
                    completion_tokens=usage.get("candidatesTokenCount", 0),
                ),
            )
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ProviderResponseError(
                f"{self.name} returned an unexpected response shape",
                details={"provider": self.name},
            ) from exc
