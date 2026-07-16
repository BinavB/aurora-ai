"""Tests for the memory layer: repositories and the store facade."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora.app.core.types import Role
from aurora.app.database import Database
from aurora.app.memory import MemoryStore, RecordKind


@pytest.fixture
async def store() -> MemoryStore:
    # A fixed clock keeps timestamps deterministic in tests.
    memory = MemoryStore(Database(), clock=lambda: "2026-01-01T00:00:00+00:00")
    await memory.open()
    return memory


async def test_conversation_history_is_ordered_and_isolated(store: MemoryStore) -> None:
    await store.add_message("a", Role.USER, "one")
    await store.add_message("b", Role.USER, "other")
    await store.add_message("a", Role.ASSISTANT, "two")

    a = [(m.role, m.content) for m in await store.conversation("a")]
    assert a == [(Role.USER, "one"), (Role.ASSISTANT, "two")]
    assert len(await store.conversation("b")) == 1


async def test_clear_conversation(store: MemoryStore) -> None:
    await store.add_message("a", Role.USER, "x")
    await store.clear_conversation("a")
    assert await store.conversation("a") == []


async def test_records_filter_by_kind_newest_first(store: MemoryStore) -> None:
    await store.remember(RecordKind.DECISION, "use sqlite", "first")
    await store.remember(RecordKind.FIX, "patch bug", "second")
    await store.remember(RecordKind.DECISION, "add index", "third")

    decisions = await store.recall(RecordKind.DECISION)
    assert [r.title for r in decisions] == ["add index", "use sqlite"]
    assert len(await store.recall()) == 3


async def test_key_value_upsert_and_items(store: MemoryStore) -> None:
    await store.kv.set("preferences", "theme", "dark")
    await store.kv.set("preferences", "theme", "light")  # upsert
    await store.kv.set("preferences", "lang", "en")
    assert await store.kv.get("preferences", "theme") == "light"
    assert await store.kv.items("preferences") == {"lang": "en", "theme": "light"}
    await store.kv.delete("preferences", "lang")
    assert await store.kv.get("preferences", "lang") is None


async def test_current_milestone_helper(store: MemoryStore) -> None:
    assert await store.current_milestone() is None
    await store.set_current_milestone("milestone-05")
    assert await store.current_milestone() == "milestone-05"


async def test_persists_to_disk_across_reconnect(tmp_path: Path) -> None:
    db_path = str(tmp_path / "aurora.db")
    first = MemoryStore(Database(db_path))
    await first.open()
    await first.add_message("s", Role.USER, "persist me")
    await first.close()

    # A brand-new store over the same file sees the data.
    second = MemoryStore(Database(db_path))
    await second.open()
    history = await second.conversation("s")
    assert [m.content for m in history] == ["persist me"]
    await second.close()
