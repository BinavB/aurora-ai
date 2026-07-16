"""Tests for the agents layer."""

from __future__ import annotations

from aurora.agents import ChatAgent
from aurora.core.types import Role
from aurora.memory import InMemoryMemory
from tests.conftest import echo_provider


async def test_chat_agent_persists_turns_and_grows_context() -> None:
    memory = InMemoryMemory()
    agent = ChatAgent(echo_provider(), memory, model="m")

    first = await agent.run("s", "hi")
    # One turn: only the user message reaches the provider.
    assert first.content == "echo[1]: hi"

    second = await agent.run("s", "again")
    # Second turn sees prior user + assistant + new user = 3 messages.
    assert second.content == "echo[3]: again"

    history = await memory.history("s")
    assert [m.role for m in history] == [
        Role.USER,
        Role.ASSISTANT,
        Role.USER,
        Role.ASSISTANT,
    ]


async def test_system_prompt_is_prepended_but_not_stored() -> None:
    memory = InMemoryMemory()
    agent = ChatAgent(echo_provider(), memory, model="m", system_prompt="be nice")

    result = await agent.run("s", "hi")
    # system + user = 2 messages sent.
    assert result.content == "echo[2]: hi"
    # But history holds only the real turn, no system message.
    assert all(m.role is not Role.SYSTEM for m in await memory.history("s"))
