"""Enforcement layer: turn AURORA's principles into checked behavior.

- ``hallucination_guard`` classifies an answer against its evidence.
- ``evidence`` reconstructs what an agent actually did.
- ``completion_gate`` blocks unverified or empty "completions".

Note: ``build_evidence`` lives in :mod:`aurora.app.guards.evidence` and is
imported from there directly — it depends on ``agents.models``, so re-exporting
it here would create an import cycle.
"""

from aurora.app.guards.completion_gate import check_completion
from aurora.app.guards.hallucination_guard import assess
from aurora.app.guards.models import (
    AgentEvidence,
    CompletionCheck,
    GuardLevel,
    GuardVerdict,
)

__all__ = [
    "assess",
    "check_completion",
    "AgentEvidence",
    "CompletionCheck",
    "GuardLevel",
    "GuardVerdict",
]
