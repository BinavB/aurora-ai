"""Hard anti-hallucination guard.

Sits between an agent's answer and the final response: it checks the claims in
the answer against the evidence the agent actually gathered and classifies the
result SAFE / WARNING / BLOCK.

- BLOCK: the answer claims a file change or a created artifact that the evidence
  does not support (a fabrication).
- WARNING: the answer hedges with unverified language ("probably", "should
  support", "I assume").
- SAFE: claims are backed by evidence and no hedging is present.

This is deterministic (no model call): it turns "never assume" from a prompt
suggestion into an enforced check.
"""

from __future__ import annotations

import os
import re

from aurora.app.guards.models import AgentEvidence, GuardLevel, GuardVerdict

# "modified app/models/User.php", "created src/x.py", ...
_FILE_CLAIM = re.compile(
    r"\b(created|added|wrote|modified|updated|edited|deleted|renamed)\b[^.\n]*?"
    r"([\w./\\-]+\.[A-Za-z0-9]{1,8})",
    re.IGNORECASE,
)
# "created a new service called X", "added a new class named Y"
_ARTIFACT_CLAIM = re.compile(
    r"\b(created|added|introduced)\b[^.\n]*?\bnew\b[^.\n]*?"
    r"\b(service|class|module|function|method|endpoint|table|component|file)\b",
    re.IGNORECASE,
)
_HEDGES = (
    "probably",
    "should support",
    "should work",
    "i think",
    "i believe",
    "might be",
    "presumably",
    "i assume",
    "likely supports",
    "as far as i know",
)


def _basenames(paths: list[str]) -> set[str]:
    return {os.path.basename(p.replace("\\", "/")).lower() for p in paths}


def assess(answer: str, evidence: AgentEvidence) -> GuardVerdict:
    """Classify ``answer`` against ``evidence`` as SAFE, WARNING, or BLOCK."""
    reasons: list[str] = []
    verified = _basenames(evidence.verified_files)
    changed = bool(evidence.verified_files) or bool(evidence.commands_executed)

    # BLOCK: a named file change that was never actually touched.
    for verb, path in _FILE_CLAIM.findall(answer):
        if os.path.basename(path.replace("\\", "/")).lower() not in verified:
            reasons.append(
                f"claims to have {verb.lower()} '{path}', but it is not in the "
                "verified evidence"
            )

    # BLOCK: claims to have created a new artifact with no change evidence at all.
    if _ARTIFACT_CLAIM.search(answer) and not changed:
        reasons.append(
            "claims to have created a new artifact without any recorded change"
        )

    if reasons:
        return GuardVerdict(level=GuardLevel.BLOCK, reasons=reasons)

    lowered = answer.lower()
    hedges = [h for h in _HEDGES if h in lowered]
    if hedges:
        return GuardVerdict(
            level=GuardLevel.WARNING,
            reasons=[f"unverified/hedged language: {', '.join(hedges)}"],
        )

    return GuardVerdict(level=GuardLevel.SAFE)
