"""The provider interface.

Higher layers depend on this Protocol, never on a concrete provider, honoring
"prefer interfaces over concrete implementations".
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from aurora.app.core.types import ChatRequest, ChatResponse


@runtime_checkable
class LLMProvider(Protocol):
    """A provider capable of producing chat completions."""

    name: str

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Produce a completion for ``request``."""
        ...

    async def aclose(self) -> None:
        """Release any resources held by the provider."""
        ...
