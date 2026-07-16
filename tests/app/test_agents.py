"""Tests for the agents layer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from aurora.app.agents import (
    CoderAgent,
    CoderInput,
    CommandAction,
    ContextBuilderAgent,
    ConversationAgent,
    ConversationTurn,
    ExecutorAgent,
    ExecutorInput,
    PlannerAgent,
    PlannerInput,
    ReviewerAgent,
    ReviewInput,
    WriteFileAction,
)
from aurora.app.context import ContextEngine, ContextRequest
from aurora.app.database import Database
from aurora.app.memory import MemoryStore
from aurora.app.tools.filesystem import filesystem_registry
from aurora.app.tools.terminal import terminal_registry
from tests.app.conftest import ScriptedProvider, echo_provider

PY = sys.executable


# --- planner --------------------------------------------------------------


async def test_planner_parses_numbered_steps() -> None:
    provider = ScriptedProvider("1. Create module\n2. Add tests\n3. Wire it up")
    plan = await PlannerAgent(provider, "m").run(PlannerInput(task="build X"))
    assert [s.index for s in plan.steps] == [1, 2, 3]
    assert plan.steps[0].description == "Create module"


# --- coder ----------------------------------------------------------------


async def test_coder_strips_code_fences() -> None:
    provider = ScriptedProvider("```python\nprint('hi')\n```")
    out = await CoderAgent(provider, "m").run(
        CoderInput(instruction="write a hello", target_path="hello.py")
    )
    assert out.path == "hello.py"
    assert out.content == "print('hi')"


# --- reviewer -------------------------------------------------------------


async def test_reviewer_extracts_findings_and_summary() -> None:
    provider = ScriptedProvider(
        "- missing error handling\n- no type hints\nSummary: needs work"
    )
    result = await ReviewerAgent(provider, "m").run(ReviewInput(code="def f(): pass"))
    assert result.findings == ["missing error handling", "no type hints"]
    assert result.summary == "needs work"


# --- conversation ---------------------------------------------------------


@pytest.fixture
async def memory() -> MemoryStore:
    store = MemoryStore(Database())
    await store.open()
    return store


async def test_conversation_persists_and_grows_context(memory: MemoryStore) -> None:
    agent = ConversationAgent(echo_provider(), "m", memory)
    first = await agent.run(ConversationTurn(session_id="s", message="hi"))
    assert first.content == "echo[1]: hi"  # only the user message this turn

    second = await agent.run(ConversationTurn(session_id="s", message="again"))
    # prior user + assistant + new user = 3 messages seen by the provider
    assert second.content == "echo[3]: again"
    assert len(await memory.conversation("s")) == 4


# --- context builder ------------------------------------------------------


async def test_context_builder_delegates_to_engine(tmp_path: Path) -> None:
    (tmp_path / "svc.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    engine = ContextEngine(filesystem_registry(str(tmp_path)))
    built = await ContextBuilderAgent(engine).run(ContextRequest(query="handler"))
    assert "svc.py" in built.files_used


# --- executor -------------------------------------------------------------


async def test_executor_applies_actions_through_tools(tmp_path: Path) -> None:
    agent = ExecutorAgent(
        filesystem_registry(str(tmp_path)), terminal_registry(str(tmp_path))
    )
    report = await agent.run(
        ExecutorInput(
            actions=[
                WriteFileAction(path="out.txt", content="data"),
                CommandAction(command=[PY, "-c", "print('done')"]),
            ]
        )
    )
    assert report.ok is True
    assert [r.kind for r in report.results] == ["write_file", "run_terminal"]
    assert (tmp_path / "out.txt").read_text() == "data"


async def test_executor_reports_failure_without_crashing(tmp_path: Path) -> None:
    agent = ExecutorAgent(
        filesystem_registry(str(tmp_path)), terminal_registry(str(tmp_path))
    )
    # A dangerous command without confirmation fails, but is reported, not raised.
    report = await agent.run(
        ExecutorInput(actions=[CommandAction(command=["rm", "-rf", "x"])])
    )
    assert report.ok is False
    assert report.results[0].detail["code"] == "confirmation_required"
