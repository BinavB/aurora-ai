"""Tests for the autonomous (ReAct) agent loop and its gated API endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aurora.app.agents.autonomous import AutonomousAgent
from aurora.app.agents.models import AutonomousInput
from aurora.app.api import create_app
from aurora.app.config.models import ProviderSettings
from aurora.app.core.types import ChatRequest, ChatResponse
from aurora.app.database import Database
from aurora.app.memory import MemoryStore
from aurora.app.providers.base import BaseProvider
from aurora.app.router import Router, build_catalog
from aurora.app.tools.filesystem import filesystem_registry
from tests.app.test_api import FakeFactory, _settings


class SequencedProvider(BaseProvider):
    """Returns pre-scripted replies in order (the last repeats if exhausted)."""

    name = "scripted"

    def __init__(self, replies: list[str]) -> None:
        super().__init__(ProviderSettings(base_url="http://seq.local"))
        self._replies = replies
        self._i = 0

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        reply = self._replies[min(self._i, len(self._replies) - 1)]
        self._i += 1
        return ChatResponse(model=request.model, content=reply)


class CyclingProvider(BaseProvider):
    """Cycles endlessly through its replies (to exercise loop detection)."""

    name = "scripted"

    def __init__(self, replies: list[str]) -> None:
        super().__init__(ProviderSettings(base_url="http://cyc.local"))
        self._replies = replies
        self._i = 0

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        reply = self._replies[self._i % len(self._replies)]
        self._i += 1
        return ChatResponse(model=request.model, content=reply)


# --- the loop -------------------------------------------------------------


async def test_agent_writes_file_then_completes(tmp_path: Path) -> None:
    replies = [
        '{"thought":"create it","tool":"write_file",'
        '"args":{"path":"hello.py","content":"print(1)\\n"}}',
        '{"thought":"all done","done":true,"answer":"Created hello.py"}',
    ]
    provider = SequencedProvider(replies)
    agent = AutonomousAgent(provider, "m", filesystem_registry(str(tmp_path)))
    report = await agent.run(AutonomousInput(task="make hello.py"))
    assert report.completed is True
    assert "Created" in report.answer
    assert (tmp_path / "hello.py").read_text() == "print(1)\n"


async def test_agent_edits_multiple_files(tmp_path: Path) -> None:
    replies = [
        '{"tool":"write_file","args":{"path":"a.txt","content":"A"}}',
        '{"tool":"write_file","args":{"path":"b.txt","content":"B"}}',
        '{"done":true,"answer":"wrote two files"}',
    ]
    agent = AutonomousAgent(
        SequencedProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="make a and b"))
    assert report.completed is True
    assert (tmp_path / "a.txt").read_text() == "A"
    assert (tmp_path / "b.txt").read_text() == "B"


async def test_agent_stops_at_step_limit(tmp_path: Path) -> None:
    # Distinct actions each turn (so the stall guard doesn't fire first).
    replies = [
        '{"tool":"read_file","args":{"path":"a"}}',
        '{"tool":"read_file","args":{"path":"b"}}',
        '{"tool":"read_file","args":{"path":"c"}}',
        '{"tool":"read_file","args":{"path":"d"}}',
    ]
    agent = AutonomousAgent(
        SequencedProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="loop", max_steps=3))
    assert report.completed is False
    assert len(report.steps) == 3
    assert "step limit" in report.answer.lower()


async def test_agent_halts_on_repeated_action(tmp_path: Path) -> None:
    replies = ['{"tool":"read_file","args":{"path":"x"}}']  # same action forever
    agent = AutonomousAgent(
        SequencedProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="spin", max_steps=10))
    assert report.completed is False
    assert "repeated" in report.steps[-1].observation


async def test_agent_reports_unknown_tool_then_recovers(tmp_path: Path) -> None:
    replies = [
        '{"tool":"frobnicate","args":{}}',
        '{"tool":"write_file","args":{"path":"r.txt","content":"ok"}}',
        '{"done":true,"answer":"wrote r.txt"}',
    ]
    agent = AutonomousAgent(
        SequencedProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="oops"))
    assert report.completed is True  # recovered and did verifiable work
    assert "unknown tool" in report.steps[0].observation


async def test_agent_runs_parallel_tool_batch(tmp_path: Path) -> None:
    # One step requests two independent writes, executed in parallel.
    replies = [
        '{"thought":"write both","actions":['
        '{"tool":"write_file","args":{"path":"a.txt","content":"A"}},'
        '{"tool":"write_file","args":{"path":"b.txt","content":"B"}}]}',
        '{"done":true,"answer":"wrote both"}',
    ]
    agent = AutonomousAgent(
        SequencedProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="make a and b"))
    assert report.completed is True
    # A single step carried both calls (fan-out), and both files landed.
    assert len(report.steps) == 2
    assert len(report.steps[0].calls) == 2
    assert all(call.ok for call in report.steps[0].calls)
    assert (tmp_path / "a.txt").read_text() == "A"
    assert (tmp_path / "b.txt").read_text() == "B"


async def test_agent_batch_reports_unknown_tool_alongside_valid(tmp_path: Path) -> None:
    replies = [
        '{"actions":['
        '{"tool":"write_file","args":{"path":"ok.txt","content":"x"}},'
        '{"tool":"frobnicate","args":{}}]}',
        '{"done":true,"answer":"done"}',
    ]
    agent = AutonomousAgent(
        SequencedProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="mixed batch"))
    calls = report.steps[0].calls
    assert (tmp_path / "ok.txt").read_text() == "x"  # the valid call still ran
    assert any(c.ok is False and "unknown tool" in c.observation for c in calls)


async def test_agent_halts_on_oscillation(tmp_path: Path) -> None:
    # Alternating actions never repeat *consecutively*, so the stall guard can't
    # fire; the whole-run repeat guard must catch the A/B/A/B loop.
    replies = [
        '{"tool":"read_file","args":{"path":"x"}}',
        '{"tool":"read_file","args":{"path":"y"}}',
    ]
    agent = AutonomousAgent(
        CyclingProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="spin", max_steps=20))
    assert report.completed is False
    assert len(report.steps) < 20  # stopped early, not at the budget
    assert "repeated" in report.steps[-1].observation


def test_parse_tolerates_code_fences_and_prose() -> None:
    fenced = 'Sure!\n```json\n{"done": true, "answer": "hi"}\n```'
    assert AutonomousAgent._parse(fenced) == {"done": True, "answer": "hi"}
    # content containing braces must round-trip (outermost braces win)
    withbraces = '{"tool":"write_file","args":{"path":"x","content":"a{b}c"}}'
    parsed = AutonomousAgent._parse(withbraces)
    assert parsed["args"]["content"] == "a{b}c"
    assert AutonomousAgent._parse("not json at all") is None


# --- API gating -----------------------------------------------------------


def _client(provider: BaseProvider, tmp_path: Path, *, enable_agent: bool) -> TestClient:
    settings = _settings()
    app = create_app(
        settings=settings,
        memory=MemoryStore(Database()),
        router=Router(build_catalog(settings)),
        factory=FakeFactory(provider),
        workspace_root=str(tmp_path),
        enable_agent=enable_agent,
    )
    return TestClient(app)


def test_agent_endpoint_absent_by_default(tmp_path: Path) -> None:
    provider = SequencedProvider(['{"done":true,"answer":"x"}'])
    with _client(provider, tmp_path, enable_agent=False) as client:
        assert client.post("/agent", json={"task": "do it"}).status_code == 404
        assert client.get("/capabilities").json()["agent"] is False


def test_agent_endpoint_runs_when_enabled(tmp_path: Path) -> None:
    replies = [
        '{"tool":"write_file","args":{"path":"out.py","content":"x = 1\\n"}}',
        '{"done":true,"answer":"wrote out.py"}',
    ]
    with _client(SequencedProvider(replies), tmp_path, enable_agent=True) as client:
        assert client.get("/capabilities").json()["agent"] is True
        res = client.post("/agent", json={"task": "create out.py"})
    assert res.status_code == 200
    body = res.json()
    assert body["report"]["completed"] is True
    assert (tmp_path / "out.py").read_text() == "x = 1\n"


def test_agent_targets_requested_workspace(tmp_path: Path) -> None:
    # The IDE passes its open folder; the agent must act there, not in the
    # server's launch directory.
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    open_dir = tmp_path / "open"
    open_dir.mkdir()
    replies = [
        '{"tool":"write_file","args":{"path":"out.py","content":"x = 1\\n"}}',
        '{"done":true,"answer":"wrote out.py"}',
    ]
    with _client(SequencedProvider(replies), server_dir, enable_agent=True) as client:
        res = client.post(
            "/agent", json={"task": "create out.py", "workspace": str(open_dir)}
        )
    assert res.status_code == 200
    assert (open_dir / "out.py").read_text() == "x = 1\n"
    assert not (server_dir / "out.py").exists()


def test_agent_invalid_workspace_returns_400(tmp_path: Path) -> None:
    provider = SequencedProvider(['{"done":true,"answer":"x"}'])
    with _client(provider, tmp_path, enable_agent=True) as client:
        res = client.post(
            "/agent", json={"task": "x", "workspace": str(tmp_path / "missing")}
        )
    assert res.status_code == 400
    assert res.json()["code"] == "validation_error"
