"""Build :class:`AgentEvidence` from an autonomous run's transcript.

Evidence is derived from what the agent actually did — the tools it called and
their outcomes — not from what it claims. It is the input to both the
hallucination guard and the completion gate.
"""

from __future__ import annotations

from aurora.app.agents.models import AgentStep, VerificationMetadata
from aurora.app.guards.models import AgentEvidence

_CHANGE_TOOLS = frozenset({"write_file", "rename_file", "delete_file"})
_READ_TOOLS = frozenset({"read_file"})
_COMMAND_TOOLS = frozenset({"run_terminal", "run_tests"})


def _command_text(tool: str, args: dict) -> str:
    """Render a command tool call as a readable command line."""
    command = args.get("command")
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    if tool == "run_tests":
        return f"pytest {args.get('path', '')}".strip()
    return str(command or tool)


def build_evidence(
    task_id: str, steps: list[AgentStep], metadata: VerificationMetadata
) -> AgentEvidence:
    """Collect files touched, commands run, and outcomes from ``steps``."""
    files: list[str] = []
    commands: list[str] = []
    results: list[str] = []
    for step in steps:
        for call in step.calls:
            results.append(f"{call.tool}:{'ok' if call.ok else 'fail'}")
            if call.tool in _CHANGE_TOOLS or call.tool in _READ_TOOLS:
                path = call.args.get("path") or call.args.get("dst")
                if path and str(path) not in files:
                    files.append(str(path))
            elif call.tool in _COMMAND_TOOLS:
                commands.append(_command_text(call.tool, call.args))
    return AgentEvidence(
        task_id=task_id,
        verified_files=files,
        commands_executed=commands,
        tool_results=results,
        assumptions=metadata.assumptions,
        confidence_score=metadata.confidence,
    )
