"""The agent abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from aurora.core.types import ChatResponse


class BaseAgent(ABC):
    """Abstract agent producing a response for a session turn."""

    @abstractmethod
    async def run(self, session_id: str, user_input: str) -> ChatResponse:
        """Advance the conversation for ``session_id`` with ``user_input``."""
        raise NotImplementedError
