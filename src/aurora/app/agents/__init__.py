"""Agents layer: single-task orchestrators.

Each agent performs one task and communicates only through injected interfaces
(providers, tools, memory, context). Agents never perform network or system I/O
directly — those go through the providers and tools layers.

Router and Memory capabilities are provided by their own layers (``router`` and
``memory``) and consumed here, rather than duplicated as pass-through agents.
"""

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.coder import CoderAgent
from aurora.app.agents.context_builder import ContextBuilderAgent
from aurora.app.agents.conversation import ConversationAgent
from aurora.app.agents.executor import ExecutorAgent
from aurora.app.agents.models import (
    ActionResult,
    CoderInput,
    CoderOutput,
    CommandAction,
    ConversationTurn,
    ExecutionReport,
    ExecutorInput,
    Plan,
    PlannerInput,
    PlanStep,
    ReviewInput,
    ReviewResult,
    WriteFileAction,
)
from aurora.app.agents.planner import PlannerAgent
from aurora.app.agents.reviewer import ReviewerAgent

__all__ = [
    "BaseAgent",
    "PlannerAgent",
    "CoderAgent",
    "ReviewerAgent",
    "ConversationAgent",
    "ContextBuilderAgent",
    "ExecutorAgent",
    "PlannerInput",
    "Plan",
    "PlanStep",
    "CoderInput",
    "CoderOutput",
    "ReviewInput",
    "ReviewResult",
    "ConversationTurn",
    "ExecutorInput",
    "ExecutionReport",
    "ActionResult",
    "WriteFileAction",
    "CommandAction",
]
