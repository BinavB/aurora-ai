"""A minimal asynchronous event bus for decoupled communication.

Layers publish domain events without knowing who consumes them, preserving the
"communicate through interfaces" principle. Handler failures are logged and
isolated so one bad subscriber cannot break publication.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from aurora.app.core.logging import get_logger

_logger = get_logger("core.events")

Handler = Callable[["Event"], Awaitable[None]]


@dataclass(frozen=True)
class Event:
    """An immutable domain event.

    Attributes:
        name: Dotted event name (e.g. ``provider.request``).
        payload: Structured, JSON-like event data.
    """

    name: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """In-process publish/subscribe bus."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, name: str, handler: Handler) -> Callable[[], None]:
        """Register ``handler`` for events named ``name``.

        Returns:
            A callable that unsubscribes the handler.
        """
        self._handlers[name].append(handler)
        return lambda: self._handlers[name].remove(handler)

    async def publish(self, event: Event) -> None:
        """Deliver ``event`` to every subscriber, isolating failures."""
        for handler in list(self._handlers.get(event.name, ())):
            try:
                await handler(event)
            except Exception:  # noqa: BLE001 - isolate subscriber failures
                _logger.exception("event_handler_failed", extra={"event": event.name})
