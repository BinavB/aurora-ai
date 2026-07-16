"""The agent abstraction.

Every agent performs exactly one task via :meth:`run`, taking a typed request
and returning a typed result. Agents collaborate only through the injected
interfaces (providers, tools, memory, context) — never by direct I/O.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAgent[RequestT, ResultT](ABC):
    """Base class for single-task agents."""

    #: Stable agent identifier.
    name: str

    @abstractmethod
    async def run(self, request: RequestT) -> ResultT:
        """Perform the agent's single task."""
        raise NotImplementedError
