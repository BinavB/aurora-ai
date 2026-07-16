"""Tests for the file-backed memory backend."""

from __future__ import annotations

from pathlib import Path

from aurora.agents import ChatAgent
from aurora.core.types import Message, Role
from aurora.memory import FileMemory
from tests.conftest import echo_provider


async def test_persists_across_instances(tmp_path: Path) -> None:
    first = FileMemory(str(tmp_path))
    await first.append("s", Message(role=Role.USER, content="remember me"))

    # A fresh instance over the same root sees prior history.
    reopened = FileMemory(str(tmp_path))
    history = await reopened.history("s")
    assert [m.content for m in history] == ["remember me"]


async def test_sessions_are_isolated_and_clearable(tmp_path: Path) -> None:
    memory = FileMemory(str(tmp_path))
    await memory.append("a", Message(role=Role.USER, content="one"))
    await memory.append("b", Message(role=Role.USER, content="two"))
    await memory.clear("a")
    assert await memory.history("a") == []
    assert [m.content for m in await memory.history("b")] == ["two"]


async def test_unsafe_session_id_stays_within_root(tmp_path: Path) -> None:
    memory = FileMemory(str(tmp_path))
    await memory.append("../escape", Message(role=Role.USER, content="x"))
    # Nothing was written outside the root.
    assert not (tmp_path.parent / "escape.jsonl").exists()
    assert list(tmp_path.glob("*.jsonl"))


async def test_is_a_drop_in_backend_for_chat_agent(tmp_path: Path) -> None:
    memory = FileMemory(str(tmp_path))
    agent = ChatAgent(echo_provider(), memory, model="m")

    await agent.run("s", "hi")
    second = await agent.run("s", "again")
    # Same behaviour as InMemoryMemory: context grows across turns.
    assert second.content == "echo[3]: again"
    assert len(await memory.history("s")) == 4
