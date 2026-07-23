"""Tests for the enforcement layer: guard, evidence, completion gate, prompts."""

from __future__ import annotations

from pathlib import Path

from aurora.app.agents.autonomous import AutonomousAgent
from aurora.app.agents.models import (
    AgentStep,
    AutonomousInput,
    ToolCall,
    VerificationMetadata,
)
from aurora.app.core.prompts import CORE_PROMPT, build_system_prompt
from aurora.app.guards import GuardLevel, assess, check_completion
from aurora.app.guards.evidence import build_evidence
from aurora.app.guards.models import AgentEvidence
from aurora.app.tools.filesystem import filesystem_registry
from tests.app.test_autonomous import SequencedProvider

# --- Phase 1: hallucination guard -----------------------------------------


def test_guard_safe_when_claim_matches_evidence() -> None:
    evidence = AgentEvidence(verified_files=["app/models/User.php"])
    verdict = assess("Modified app/models/User.php to fix the method.", evidence)
    assert verdict.level is GuardLevel.SAFE


def test_guard_warns_on_hedged_language() -> None:
    verdict = assess("Laravel probably supports this.", AgentEvidence())
    assert verdict.level is GuardLevel.WARNING


def test_guard_blocks_unverified_creation() -> None:
    verdict = assess("Created a new service called PaymentManager.", AgentEvidence())
    assert verdict.level is GuardLevel.BLOCK


def test_guard_blocks_claim_about_untouched_file() -> None:
    evidence = AgentEvidence(verified_files=["other.py"], tool_results=["read_file:ok"])
    verdict = assess("Modified src/pay.py to add logging.", evidence)
    assert verdict.level is GuardLevel.BLOCK


# --- Phase 2: evidence tracking -------------------------------------------


def test_build_evidence_collects_files_commands_and_metadata() -> None:
    steps = [
        AgentStep(
            index=1,
            calls=[ToolCall(tool="read_file", args={"path": "a.py"}, ok=True)],
        ),
        AgentStep(
            index=2,
            calls=[
                ToolCall(
                    tool="write_file", args={"path": "b.py", "content": "x"}, ok=True
                )
            ],
        ),
        AgentStep(
            index=3,
            calls=[ToolCall(tool="run_tests", args={"path": "tests"}, ok=True)],
        ),
    ]
    evidence = build_evidence(
        "task", steps, VerificationMetadata(confidence=80, assumptions=["redis up"])
    )
    assert "a.py" in evidence.verified_files
    assert "b.py" in evidence.verified_files
    assert any("pytest" in c for c in evidence.commands_executed)
    assert evidence.confidence_score == 80
    assert evidence.assumptions == ["redis up"]


# --- Phase 3: completion gate ---------------------------------------------


def test_gate_blocks_completion_without_evidence() -> None:
    evidence = AgentEvidence()
    check = check_completion(evidence, assess("all done", evidence))
    assert check.passed is False


def test_gate_passes_with_change_evidence() -> None:
    evidence = AgentEvidence(verified_files=["b.py"], tool_results=["write_file:ok"])
    check = check_completion(evidence, assess("wrote b.py", evidence))
    assert check.passed is True
    assert check.implemented is True


def test_gate_blocks_when_guard_blocks() -> None:
    evidence = AgentEvidence(verified_files=["b.py"], tool_results=["write_file:ok"])
    verdict = assess("Modified ghost.py to fix it.", evidence)
    assert verdict.level is GuardLevel.BLOCK
    assert check_completion(evidence, verdict).passed is False


# --- autonomous agent enforcement -----------------------------------------


async def test_autonomous_gate_blocks_empty_completion(tmp_path: Path) -> None:
    # Declaring done with no tool use must not be accepted as success.
    agent = AutonomousAgent(
        SequencedProvider(['{"done":true,"answer":"all done"}']),
        "m",
        filesystem_registry(str(tmp_path)),
    )
    report = await agent.run(AutonomousInput(task="do it"))
    assert report.completed is False
    assert report.completion is not None and report.completion.passed is False


async def test_autonomous_gate_passes_with_real_work(tmp_path: Path) -> None:
    replies = [
        '{"tool":"write_file","args":{"path":"z.py","content":"x = 1\\n"}}',
        '{"done":true,"answer":"wrote z.py"}',
    ]
    agent = AutonomousAgent(
        SequencedProvider(replies), "m", filesystem_registry(str(tmp_path))
    )
    report = await agent.run(AutonomousInput(task="make z"))
    assert report.completed is True
    assert report.completion is not None and report.completion.passed is True
    assert report.evidence is not None and "z.py" in report.evidence.verified_files


# --- Phase 4: layered prompts ---------------------------------------------


def test_core_prompt_is_the_default_layer() -> None:
    assert build_system_prompt() == CORE_PROMPT


def test_task_layer_is_appended_for_a_kind() -> None:
    prompt = build_system_prompt("plan")
    assert prompt.startswith(CORE_PROMPT)
    assert "concrete, ordered" in prompt
