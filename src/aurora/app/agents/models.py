"""Typed request/result models for the agents."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from aurora.app.core.types import Message


# --- planner --------------------------------------------------------------
class PlanStep(BaseModel):
    """A single planned step."""

    index: int
    description: str


class PlannerInput(BaseModel):
    """Input for the planner."""

    task: str = Field(min_length=1)
    context_messages: list[Message] = Field(default_factory=list)


class Plan(BaseModel):
    """An ordered plan for a task."""

    task: str
    steps: list[PlanStep]


# --- coder ----------------------------------------------------------------
class CoderInput(BaseModel):
    """Input for the coder."""

    instruction: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    context_messages: list[Message] = Field(default_factory=list)


class CoderOutput(BaseModel):
    """Proposed full contents for a single file (not yet written)."""

    path: str
    content: str


# --- reviewer -------------------------------------------------------------
class ReviewInput(BaseModel):
    """Input for the reviewer."""

    code: str = Field(min_length=1)
    focus: str = "correctness, clarity, and bugs"


class ReviewResult(BaseModel):
    """Structured review output."""

    summary: str
    findings: list[str]


# --- conversation ---------------------------------------------------------
class ConversationTurn(BaseModel):
    """A single conversational turn."""

    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


# --- executor -------------------------------------------------------------
class WriteFileAction(BaseModel):
    """Action: write a file via the filesystem tools."""

    kind: Literal["write_file"] = "write_file"
    path: str
    content: str


class CommandAction(BaseModel):
    """Action: run a command via the terminal tools."""

    kind: Literal["run_terminal"] = "run_terminal"
    command: list[str] = Field(min_length=1)
    confirm: bool = False


Action = Annotated[WriteFileAction | CommandAction, Field(discriminator="kind")]


class ExecutorInput(BaseModel):
    """A batch of actions to execute in order."""

    actions: list[Action]


class ActionResult(BaseModel):
    """The outcome of one executed action."""

    kind: str
    tool: str
    ok: bool
    detail: dict | None = None


class ExecutionReport(BaseModel):
    """The combined outcome of an execution batch."""

    results: list[ActionResult]
    ok: bool


# --- autonomous agent (ReAct loop) ----------------------------------------
class ToolCall(BaseModel):
    """One tool invocation within a step (a step may run several in parallel)."""

    tool: str
    args: dict = Field(default_factory=dict)
    ok: bool | None = None
    observation: str = ""


class AgentStep(BaseModel):
    """One iteration of the autonomous loop: think, act, observe.

    A step may invoke several tools at once (``calls``, run in parallel). The
    scalar ``tool``/``args``/``ok``/``observation`` mirror the single call when a
    step makes exactly one, preserving the simple single-tool view.
    """

    index: int
    thought: str = ""
    tool: str | None = None
    args: dict = Field(default_factory=dict)
    ok: bool | None = None
    observation: str = ""
    calls: list[ToolCall] = Field(default_factory=list)


class AutonomousInput(BaseModel):
    """A goal for the autonomous agent to accomplish via tools."""

    task: str = Field(min_length=1)
    max_steps: int = Field(default=12, ge=1, le=40)
    context_messages: list[Message] = Field(default_factory=list)


class AutonomousReport(BaseModel):
    """The transcript and outcome of an autonomous run."""

    answer: str
    completed: bool
    steps: list[AgentStep]
