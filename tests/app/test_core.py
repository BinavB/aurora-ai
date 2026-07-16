"""Tests for the core layer: exceptions, logging, events, container, types."""

from __future__ import annotations

import json
import logging

import pytest

from aurora.app.core import (
    Container,
    Event,
    EventBus,
    ProviderError,
    ProviderRequestError,
    ValidationError,
)
from aurora.app.core.exceptions import AuroraError, ConfigurationError
from aurora.app.core.logging import JsonFormatter, get_logger, redact
from aurora.app.core.types import ChatRequest, Message, Role, Usage

# --- exceptions -----------------------------------------------------------


def test_exception_hierarchy_and_serialization() -> None:
    err = ProviderRequestError("boom", details={"provider": "openai"})
    assert isinstance(err, ProviderError)
    assert isinstance(err, AuroraError)
    assert err.to_dict() == {
        "code": "provider_request_error",
        "message": "boom",
        "details": {"provider": "openai"},
    }


def test_validation_error_default_code() -> None:
    assert ValidationError("bad").code == "validation_error"


# --- logging / redaction --------------------------------------------------


def test_redact_scrubs_sensitive_keys() -> None:
    cleaned = redact(
        {"api_key": "sk-secret", "nested": {"password": "p"}, "model": "gpt"}
    )
    assert cleaned["api_key"] == "***redacted***"
    assert cleaned["nested"]["password"] == "***redacted***"
    assert cleaned["model"] == "gpt"


def test_json_formatter_emits_redacted_context() -> None:
    record = logging.LogRecord(
        "aurora.test", logging.INFO, __file__, 1, "hello", None, None
    )
    record.api_key = "sk-leak"
    record.model = "gpt"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello"
    assert payload["context"]["api_key"] == "***redacted***"
    assert payload["context"]["model"] == "gpt"


def test_get_logger_is_namespaced() -> None:
    assert get_logger("providers.openai").name == "aurora.providers.openai"


# --- events ---------------------------------------------------------------


async def test_event_bus_publishes_and_unsubscribes() -> None:
    bus = EventBus()
    seen: list[str] = []

    async def handler(event: Event) -> None:
        seen.append(event.payload["v"])

    unsubscribe = bus.subscribe("x", handler)
    await bus.publish(Event("x", {"v": "a"}))
    unsubscribe()
    await bus.publish(Event("x", {"v": "b"}))
    assert seen == ["a"]


async def test_event_bus_isolates_handler_failures() -> None:
    bus = EventBus()
    delivered: list[str] = []

    async def bad(_: Event) -> None:
        raise RuntimeError("nope")

    async def good(_: Event) -> None:
        delivered.append("ok")

    bus.subscribe("x", bad)
    bus.subscribe("x", good)
    await bus.publish(Event("x"))  # must not raise
    assert delivered == ["ok"]


# --- container ------------------------------------------------------------


def test_container_resolves_instances_and_factories() -> None:
    container = Container()
    container.register_instance("greeting", "hi")
    calls: list[int] = []

    def factory(_: Container) -> object:
        calls.append(1)
        return object()

    container.register_factory("svc", factory)
    assert container.resolve("greeting") == "hi"
    first = container.resolve("svc")
    second = container.resolve("svc")
    assert first is second  # cached as singleton
    assert len(calls) == 1


def test_container_missing_key_raises() -> None:
    with pytest.raises(ConfigurationError):
        Container().resolve("absent")


# --- types ----------------------------------------------------------------


def test_usage_total() -> None:
    assert Usage(prompt_tokens=3, completion_tokens=4).total_tokens == 7


def test_chat_request_validation() -> None:
    with pytest.raises(ValueError):
        ChatRequest(model="m", messages=[])
    with pytest.raises(ValueError):
        ChatRequest(
            model="m",
            messages=[Message(role=Role.USER, content="hi")],
            temperature=9.0,
        )
