"""Typed models for terminal execution."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CommandResult(BaseModel):
    """The captured outcome of a command execution.

    Attributes:
        stdout: Captured standard output.
        stderr: Captured standard error.
        exit_code: Process exit code (``-1`` when the command timed out).
        duration_seconds: Wall-clock execution time.
        timed_out: Whether the command was killed for exceeding its timeout.
    """

    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    timed_out: bool = False


class StreamLine(BaseModel):
    """A single line emitted while streaming a command."""

    stream: str  # "stdout" or "stderr"
    text: str


class RunTerminalInput(BaseModel):
    """Input for running a command as an argument vector (no shell)."""

    command: list[str] = Field(min_length=1)
    cwd: str | None = None
    timeout: float = Field(default=30.0, gt=0.0, le=600.0)
    confirm: bool = False


class RunTestsInput(BaseModel):
    """Input for running the test suite via pytest."""

    path: str | None = None
    extra_args: list[str] = Field(default_factory=list)
    timeout: float = Field(default=300.0, gt=0.0, le=600.0)
