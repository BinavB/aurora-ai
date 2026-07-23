"""Tests for the agentic pipeline: Intent -> Plan -> Execute -> Verify -> Learn."""

from __future__ import annotations

from pathlib import Path

from aurora.app.agents.models import AutonomousReport, Plan, PlanStep
from aurora.app.database import Database
from aurora.app.memory import MemoryStore
from aurora.app.memory.models import RecordKind
from aurora.app.services import (
    AgentPipeline,
    ExecutionService,
    MemoryService,
    TaskService,
    VerificationService,
)
from aurora.app.services.models import (
    AgentResult,
    MemoryReceipt,
    PlanResult,
    TaskSpec,
    VerificationReport,
)
from tests.app.test_autonomous import SequencedProvider
from tests.app.test_autonomous import _client as _agent_client
from tests.app.test_services import FakeFactory, ScriptedProvider, _router


def _agent_result(completed: bool, answer: str = "done") -> AgentResult:
    return AgentResult(
        provider="p",
        model="m",
        report=AutonomousReport(answer=answer, completed=completed, steps=[]),
    )


# --- Intent ---------------------------------------------------------------


def test_task_service_understands_request() -> None:
    spec = TaskService().understand("  Explain how routing works  ")
    assert spec.objective == "Explain how routing works"
    assert spec.intent == "explain"  # classify_intent picks EXPLAIN


# --- Execute --------------------------------------------------------------


class _RecordingAutonomous:
    """Stub autonomous service capturing the instruction it was handed."""

    def __init__(self) -> None:
        self.instruction: str | None = None

    async def run(self, task: str, workspace: str, **_: object) -> AgentResult:
        self.instruction = task
        return _agent_result(True, "did it")


async def test_execution_service_frames_objective_and_plan() -> None:
    auto = _RecordingAutonomous()
    service = ExecutionService(auto)  # type: ignore[arg-type]
    plan = Plan(
        task="t",
        steps=[
            PlanStep(index=1, description="write file"),
            PlanStep(index=2, description="run tests"),
        ],
    )
    result = await service.execute(
        TaskSpec(objective="build X", intent="implement"), plan, "/ws"
    )

    assert "build X" in auto.instruction
    assert "1. write file" in auto.instruction and "2. run tests" in auto.instruction
    assert result.report.completed is True


# --- Verify ---------------------------------------------------------------


async def test_verification_service_reads_pass() -> None:
    service = VerificationService(
        _router(), FakeFactory(ScriptedProvider("PASS\nlooks good"))
    )
    report = await service.verify(
        TaskSpec(objective="x", intent="implement"), _agent_result(True)
    )
    assert report.passed is True
    assert report.issues == []


async def test_verification_service_reads_fail_with_issues() -> None:
    reply = "FAIL\n- missing tests\n- no error handling"
    service = VerificationService(_router(), FakeFactory(ScriptedProvider(reply)))
    report = await service.verify(
        TaskSpec(objective="x", intent="implement"), _agent_result(False)
    )
    assert report.passed is False
    assert report.issues == ["missing tests", "no error handling"]


# --- Learn ----------------------------------------------------------------


async def test_memory_service_records_fix_on_pass() -> None:
    store = MemoryStore(Database())
    await store.open()
    receipt = await MemoryService(store).learn(
        TaskSpec(objective="add caching", intent="implement"),
        _agent_result(True),
        VerificationReport(provider="p", model="m", passed=True, summary="PASS"),
    )
    assert receipt.stored is True and receipt.record_id is not None
    fixes = await store.recall(RecordKind.FIX)
    assert fixes and fixes[0].title == "add caching"


async def test_memory_service_records_issue_on_fail() -> None:
    store = MemoryStore(Database())
    await store.open()
    await MemoryService(store).learn(
        TaskSpec(objective="broken thing", intent="implement"),
        _agent_result(False),
        VerificationReport(
            provider="p", model="m", passed=False, summary="FAIL", issues=["bug"]
        ),
    )
    issues = await store.recall(RecordKind.ISSUE)
    assert issues and issues[0].title == "broken thing"


# --- full pipeline (stubbed stages) ---------------------------------------


class _StubPlanning:
    async def plan(self, task: str, workspace: str, **_: object) -> PlanResult:
        return PlanResult(
            provider="p",
            model="m",
            plan=Plan(task=task, steps=[PlanStep(index=1, description="s1")]),
            context_files=[],
        )


class _StubExecution:
    def __init__(self) -> None:
        self.called = False

    async def execute(
        self, spec, plan, workspace, **_: object
    ) -> AgentResult:  # noqa: ANN001
        self.called = True
        return _agent_result(True, "executed")


class _StubVerification:
    async def verify(
        self, spec, execution, **_: object
    ) -> VerificationReport:  # noqa: ANN001
        return VerificationReport(provider="p", model="m", passed=True, summary="PASS")


class _StubMemory:
    def __init__(self) -> None:
        self.learned = False

    async def learn(self, spec, execution, verification) -> MemoryReceipt:  # noqa: ANN001
        self.learned = True
        return MemoryReceipt(stored=True, record_id=7)


class _CountingExecution:
    def __init__(self) -> None:
        self.count = 0

    async def execute(
        self, spec, plan, workspace, **_: object
    ) -> AgentResult:  # noqa: ANN001
        self.count += 1
        return _agent_result(True, "executed")


class _FlakyVerification:
    """Fails verification until the ``pass_on``-th call."""

    def __init__(self, pass_on: int) -> None:
        self.calls = 0
        self._pass_on = pass_on

    async def verify(
        self, spec, execution, **_: object
    ) -> VerificationReport:  # noqa: ANN001
        self.calls += 1
        passed = self.calls >= self._pass_on
        return VerificationReport(provider="p", model="m", passed=passed, summary="x")


async def test_pipeline_retries_until_verified() -> None:
    execution, verify = _CountingExecution(), _FlakyVerification(pass_on=2)
    pipeline = AgentPipeline(
        TaskService(), _StubPlanning(), execution, verify, _StubMemory()
    )  # type: ignore[arg-type]

    result = await pipeline.run("do it", "/ws")

    assert result.status == "COMPLETE"
    assert execution.count == 2  # escalated to a second attempt
    assert [a.verified for a in result.attempts] == [False, True]
    assert result.attempts[1].strategy == "debugger"


async def test_pipeline_needs_input_when_all_attempts_fail() -> None:
    execution, verify = _CountingExecution(), _FlakyVerification(pass_on=99)
    pipeline = AgentPipeline(
        TaskService(), _StubPlanning(), execution, verify, _StubMemory()
    )  # type: ignore[arg-type]

    result = await pipeline.run("do it", "/ws")

    assert result.status == "NEEDS_INPUT"
    assert len(result.attempts) == 3  # exhausted the escalation ladder
    assert execution.count == 3


async def test_pipeline_runs_every_stage_in_order() -> None:
    execution, memory = _StubExecution(), _StubMemory()
    pipeline = AgentPipeline(
        TaskService(), _StubPlanning(), execution, _StubVerification(), memory
    )  # type: ignore[arg-type]

    result = await pipeline.run("implement a feature", "/ws")

    assert result.objective == "implement a feature"
    assert result.plan.steps[0].description == "s1"
    assert result.execution.report.answer == "executed"
    assert result.verification.passed is True
    assert result.memory.record_id == 7
    assert execution.called and memory.learned  # both later stages ran


# --- API endpoint (gated) -------------------------------------------------


def test_task_endpoint_absent_when_agent_disabled(tmp_path: Path) -> None:
    provider = SequencedProvider(['{"done":true,"answer":"x"}'])
    with _agent_client(provider, tmp_path, enable_agent=False) as client:
        assert client.post("/task", json={"task": "do it"}).status_code == 404


def test_task_endpoint_runs_full_pipeline_when_enabled(tmp_path: Path) -> None:
    replies = [
        "1. Write out.py\n2. Verify the file",  # planner
        '{"tool":"write_file","args":{"path":"out.py","content":"x = 1\\n"}}',  # execute
        '{"done":true,"answer":"wrote out.py"}',  # execute done
        "PASS\nSummary: file created as required",  # verify
    ]
    with _agent_client(SequencedProvider(replies), tmp_path, enable_agent=True) as client:
        res = client.post("/task", json={"task": "create out.py"})
    assert res.status_code == 200
    body = res.json()
    assert body["execution"]["report"]["completed"] is True
    assert body["verification"]["passed"] is True
    assert (tmp_path / "out.py").read_text() == "x = 1\n"
