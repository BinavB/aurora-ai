"""A small dependency-injection container.

Supports registering singleton instances and lazy factories keyed by a string
or a type. Enables the architecture's dependency-injection and
"replaceable without affecting the rest" requirements without global state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, overload

from aurora.app.core.exceptions import ConfigurationError

T = TypeVar("T")

Key = str | type


def _normalize(key: Key) -> str:
    return key if isinstance(key, str) else f"{key.__module__}.{key.__qualname__}"


class Container:
    """Registry of singletons and factories resolvable by key or type."""

    def __init__(self) -> None:
        self._singletons: dict[str, Any] = {}
        self._factories: dict[str, Callable[[Container], Any]] = {}

    def register_instance(self, key: Key, instance: Any) -> None:
        """Register an already-constructed singleton under ``key``."""
        self._singletons[_normalize(key)] = instance

    def register_factory(self, key: Key, factory: Callable[[Container], Any]) -> None:
        """Register a lazy factory; its result is cached as a singleton."""
        self._factories[_normalize(key)] = factory

    @overload
    def resolve(self, key: type[T]) -> T: ...
    @overload
    def resolve(self, key: str) -> Any: ...

    def resolve(self, key: Key) -> Any:
        """Return the instance for ``key``, constructing it if needed.

        Raises:
            ConfigurationError: If nothing is registered for ``key``.
        """
        name = _normalize(key)
        if name in self._singletons:
            return self._singletons[name]
        if name in self._factories:
            instance = self._factories[name](self)
            self._singletons[name] = instance
            return instance
        raise ConfigurationError(f"Nothing registered for '{name}'")

    def has(self, key: Key) -> bool:
        """Return whether anything is registered for ``key``."""
        name = _normalize(key)
        return name in self._singletons or name in self._factories
