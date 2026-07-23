"""The autonomous completion gate.

Before an autonomous run may report success, this gate checks the evidence: was
anything actually implemented, were files inspected, tests run, errors checked,
assumptions documented? Completion is **blocked** when the hallucination guard
returns BLOCK or when the agent produced no verifiable activity at all — turning
"never claim done without evidence" into an enforced rule. The finer checks are
reported as reasons so the agent can address them on the next iteration.
"""

from __future__ import annotations

from aurora.app.guards.models import (
    AgentEvidence,
    CompletionCheck,
    GuardLevel,
    GuardVerdict,
)

_CHANGE_TOOLS = ("write_file", "rename_file", "delete_file")


def check_completion(evidence: AgentEvidence, verdict: GuardVerdict) -> CompletionCheck:
    """Decide whether an autonomous run may be marked complete."""
    implemented = any(
        result.endswith(":ok") and result.split(":", 1)[0] in _CHANGE_TOOLS
        for result in evidence.tool_results
    )
    inspected = bool(evidence.verified_files)
    tested = any("pytest" in cmd or "test" in cmd for cmd in evidence.commands_executed)
    errors_checked = tested or any(r.endswith(":fail") for r in evidence.tool_results)
    assumptions_documented = bool(evidence.assumptions)
    did_something = bool(
        evidence.verified_files or evidence.commands_executed or evidence.tool_results
    )

    reasons: list[str] = []
    if verdict.level is GuardLevel.BLOCK:
        reasons.extend(verdict.reasons)
    if not did_something:
        reasons.append("no tools were used — nothing was verified or changed")
    if not tested:
        reasons.append("no tests were run to validate the change")
    if not assumptions_documented:
        reasons.append("assumptions were not documented")

    # Hard gate: never complete on a BLOCK or with zero verifiable activity.
    passed = verdict.level is not GuardLevel.BLOCK and did_something
    return CompletionCheck(
        implemented=implemented,
        inspected=inspected,
        tested=tested,
        errors_checked=errors_checked,
        assumptions_documented=assumptions_documented,
        passed=passed,
        reasons=reasons,
    )
