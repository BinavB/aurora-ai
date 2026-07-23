"""Tests for the AURORA engineering-behavior system (prompt + agent upgrades)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aurora.app.agents.autonomous import AutonomousAgent
from aurora.app.agents.coder import CoderAgent
from aurora.app.agents.models import (
    AutonomousInput,
    CoderInput,
    PlannerInput,
    ReviewInput,
)
from aurora.app.agents.planner import PlannerAgent
from aurora.app.agents.reviewer import ReviewerAgent
from aurora.app.api import create_app
from aurora.app.config.models import ProviderSettings
from aurora.app.core.prompts import AURORA_SYSTEM_PROMPT
from aurora.app.core.types import ChatRequest, ChatResponse, Role
from aurora.app.database import Database
from aurora.app.memory import MemoryStore
from aurora.app.providers.base import BaseProvider
from aurora.app.router import Router, build_catalog
from aurora.app.tools.filesystem import filesystem_registry
from tests.app.test_api import FakeFactory, _settings

_SENTINEL = "SENTINEL-BASE-PROMPT"


class CapturingProvider(BaseProvider):
    """Records the messages of the most recent call for inspection."""

    name = "capture"

    def __init__(self, reply: str = "ok") -> None:
        super().__init__(ProviderSettings(base_url="http://cap.local"))
        self.system_text = ""
        self._reply = reply

    async def _chat(self, request: ChatRequest) -> ChatResponse:
        self.system_text = "\n".join(
            m.content for m in request.messages if m.role is Role.SYSTEM
        )
        return ChatResponse(model=request.model, content=self._reply)


# --- Phase 1: the prompt --------------------------------------------------


def test_system_prompt_encodes_core_principles() -> None:
    text = AURORA_SYSTEM_PROMPT.lower()
    assert "aurora" in text
    assert "never invent" in text  # anti-hallucination
    assert "verify" in text  # verification-first
    assert "understand" in text and "plan" in text  # workflow


# --- every agent inherits the base prompt (composed, not duplicated) ------


async def test_planner_agent_inherits_base_prompt() -> None:
    provider = CapturingProvider("1. step one")
    await PlannerAgent(provider, "m", _SENTINEL).run(PlannerInput(task="do it"))
    assert _SENTINEL in provider.system_text


async def test_reviewer_agent_inherits_base_prompt() -> None:
    provider = CapturingProvider("- issue\nSummary: ok")
    await ReviewerAgent(provider, "m", _SENTINEL).run(ReviewInput(code="x = 1"))
    assert _SENTINEL in provider.system_text


async def test_coder_agent_inherits_base_prompt() -> None:
    provider = CapturingProvider("print('x')")
    await CoderAgent(provider, "m", _SENTINEL).run(
        CoderInput(instruction="make it", target_path="a.py")
    )
    assert _SENTINEL in provider.system_text


async def test_autonomous_agent_inherits_base_prompt(tmp_path: Path) -> None:
    provider = CapturingProvider('{"done": true, "answer": "done"}')
    agent = AutonomousAgent(provider, "m", filesystem_registry(str(tmp_path)), _SENTINEL)
    await agent.run(AutonomousInput(task="do it", max_steps=1))
    assert _SENTINEL in provider.system_text


def test_agent_without_prompt_still_works() -> None:
    # Composition is optional: no base prompt -> just the role prompt.
    async def _run() -> str:
        provider = CapturingProvider("1. step")
        await PlannerAgent(provider, "m").run(PlannerInput(task="t"))
        return provider.system_text

    import asyncio

    assert "senior software planner" in asyncio.run(_run())


# --- Phase 2: create_app injects the default into every endpoint ----------


def test_create_app_injects_default_prompt(tmp_path: Path) -> None:
    provider = CapturingProvider("- x\nSummary: ok")
    settings = _settings()
    app = create_app(
        settings=settings,
        memory=MemoryStore(Database()),
        router=Router(build_catalog(settings)),
        factory=FakeFactory(provider),
        workspace_root=str(tmp_path),
    )
    with TestClient(app) as client:
        assert client.post("/review", json={"code": "def f(): pass"}).status_code == 200
    # The reviewer's system message carries the injected AURORA prompt.
    assert "You are AURORA" in provider.system_text


# --- Phase 3/4/5: autonomous rules, phases, and verification metadata -----


def test_autonomous_system_states_verification_rules(tmp_path: Path) -> None:
    provider = CapturingProvider('{"done": true, "answer": "x"}')
    agent = AutonomousAgent(provider, "m", filesystem_registry(str(tmp_path)))
    # trigger one call so the system message is captured
    import asyncio

    asyncio.run(agent.run(AutonomousInput(task="t", max_steps=1)))
    text = provider.system_text.lower()
    assert "before modifying a file, read it first" in text
    assert "never blindly overwrite" in text
    assert "analyze" in text and "verify" in text  # the state machine


async def test_autonomous_records_phase_and_metadata(tmp_path: Path) -> None:
    from tests.app.test_autonomous import SequencedProvider

    replies = [
        '{"phase":"EXECUTE","tool":"write_file","args":{"path":"a.txt","content":"A"}}',
        '{"phase":"COMPLETE","done":true,"answer":"done",'
        '"confidence":90,"verified":["file written"],'
        '"assumptions":["path is valid"],"risks":["none"],"unknowns":["prod config"]}',
    ]
    agent = AutonomousAgent(
        SequencedProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="make a.txt"))

    assert report.completed is True
    assert report.steps[0].phase == "EXECUTE"
    assert report.steps[-1].phase == "COMPLETE"
    assert report.metadata.confidence == 90
    assert report.metadata.verified == ["file written"]
    assert report.metadata.assumptions == ["path is valid"]
    assert report.metadata.unknowns == ["prod config"]


async def test_autonomous_metadata_defaults_when_absent(tmp_path: Path) -> None:
    # A plain done action (no metadata) yields a safe zero-confidence report.
    from tests.app.test_autonomous import SequencedProvider

    agent = AutonomousAgent(
        SequencedProvider(['{"done":true,"answer":"ok"}']),
        "m",
        filesystem_registry(str(tmp_path)),
    )
    report = await agent.run(AutonomousInput(task="t"))
    assert report.metadata.confidence == 0
    assert report.metadata.verified == []
