"""Executor agent: apply actions strictly through tools.

The executor performs no filesystem or terminal I/O itself; every action is
dispatched to the appropriate tool registry, and each tool's structured result
is recorded. This keeps side effects confined to the tool layer.
"""

from __future__ import annotations

from aurora.app.agents.base import BaseAgent
from aurora.app.agents.models import (
    ActionResult,
    CommandAction,
    ExecutionReport,
    ExecutorInput,
    WriteFileAction,
)
from aurora.app.tools.models import ToolResult
from aurora.app.tools.registry import ToolRegistry


class ExecutorAgent(BaseAgent[ExecutorInput, ExecutionReport]):
    """Execute a batch of actions via the filesystem and terminal tools."""

    name = "executor"

    def __init__(self, filesystem: ToolRegistry, terminal: ToolRegistry) -> None:
        self._fs = filesystem
        self._terminal = terminal

    async def run(self, request: ExecutorInput) -> ExecutionReport:
        results: list[ActionResult] = []
        for action in request.actions:
            result = await self._dispatch(action)
            results.append(
                ActionResult(
                    kind=action.kind,
                    tool=result.tool,
                    ok=result.ok,
                    detail=result.data if result.ok else result.error,
                )
            )
        return ExecutionReport(results=results, ok=all(r.ok for r in results))

    async def _dispatch(self, action: WriteFileAction | CommandAction) -> ToolResult:
        if isinstance(action, WriteFileAction):
            return await self._fs.invoke(
                "write_file", {"path": action.path, "content": action.content}
            )
        return await self._terminal.invoke(
            "run_terminal",
            {"command": action.command, "confirm": action.confirm},
        )
