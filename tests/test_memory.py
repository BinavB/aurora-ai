"""Tests for the memory layer."""

from __future__ import annotations

from aurora.core.types import Message, Role
from aurora.memory import InMemoryMemory


async def test_append_and_history_are_isolated_per_session() -> None:
    memory = InMemoryMemory()
    await memory.append("a", Message(role=Role.USER, content="one"))
    await memory.append("b", Message(role=Role.USER, content="two"))
    await memory.append("a", Message(role=Role.ASSISTANT, content="three"))

    a = [m.content for m in await memory.history("a")]
    b = [m.content for m in await memory.history("b")]
    assert a == ["one", "three"]
    assert b == ["two"]


async def test_history_returns_a_copy() -> None:
    memory = InMemoryMemory()
    await memory.append("s", Message(role=Role.USER, content="x"))
    snapshot = await memory.history("s")
    snapshot.clear()
    assert len(await memory.history("s")) == 1


async def test_clear() -> None:
    memory = InMemoryMemory()
    await memory.extend(
        "s",
        [Message(role=Role.USER, content="x"), Message(role=Role.ASSISTANT, content="y")],
    )
    await memory.clear("s")
    assert await memory.history("s") == []
