"""Concrete terminal tools.

Terminal tools are the only sanctioned way to execute commands. They capture
structured results and require explicit confirmation for dangerous commands.
"""

from __future__ import annotations

import sys
from pathlib import Path

from aurora.app.core.exceptions import ConfirmationRequiredError
from aurora.app.tools.base import BaseTool
from aurora.app.tools.models import Permission, ToolMetadata
from aurora.app.tools.terminal.models import (
    CommandResult,
    RunTerminalInput,
    RunTestsInput,
)
from aurora.app.tools.terminal.runner import TerminalRunner
from aurora.app.tools.terminal.safety import dangerous_reason

_CATEGORY = "terminal"


class _TerminalTool(BaseTool):
    """Base for terminal tools sharing a runner."""

    def __init__(self, workdir: str | Path) -> None:
        self._runner = TerminalRunner(workdir)
        super().__init__()


class RunTerminalTool(_TerminalTool):
    """Run a command as an argument vector and capture its result."""

    metadata = ToolMetadata(
        name="run_terminal",
        description="Execute a command (argument vector, no shell) and capture output.",
        category=_CATEGORY,
        permissions=frozenset({Permission.EXECUTE}),
    )
    input_model = RunTerminalInput
    output_model = CommandResult

    async def execute(self, payload: RunTerminalInput) -> CommandResult:
        reason = dangerous_reason(payload.command)
        if reason and not payload.confirm:
            raise ConfirmationRequiredError(
                f"Refusing to run dangerous command without confirmation: {reason}",
                details={"command": payload.command, "reason": reason},
            )
        return await self._runner.run(
            payload.command, cwd=payload.cwd, timeout=payload.timeout
        )


class RunTestsTool(_TerminalTool):
    """Run the test suite with pytest and capture its result."""

    metadata = ToolMetadata(
        name="run_tests",
        description="Run pytest within the project and capture the result.",
        category=_CATEGORY,
        permissions=frozenset({Permission.EXECUTE}),
    )
    input_model = RunTestsInput
    output_model = CommandResult

    async def execute(self, payload: RunTestsInput) -> CommandResult:
        command = [sys.executable, "-m", "pytest"]
        if payload.path:
            command.append(payload.path)
        command.extend(payload.extra_args)
        return await self._runner.run(command, timeout=payload.timeout)
