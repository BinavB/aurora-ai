"""Terminal tools: the only sanctioned path to command execution.

Commands run as argument vectors (never a shell), capturing stdout, stderr,
exit code, and duration. Dangerous commands require explicit confirmation.
"""

from aurora.app.tools.registry import ToolRegistry
from aurora.app.tools.terminal.models import CommandResult, StreamLine
from aurora.app.tools.terminal.runner import TerminalRunner
from aurora.app.tools.terminal.safety import dangerous_reason
from aurora.app.tools.terminal.tools import RunTerminalTool, RunTestsTool


def terminal_registry(workdir: str) -> ToolRegistry:
    """Build a registry of the terminal tools bound to ``workdir``.

    Args:
        workdir: Directory that bounds command working directories.

    Returns:
        A registry containing the run-terminal and run-tests tools.
    """
    return ToolRegistry([RunTerminalTool(workdir), RunTestsTool(workdir)])


__all__ = [
    "TerminalRunner",
    "CommandResult",
    "StreamLine",
    "RunTerminalTool",
    "RunTestsTool",
    "dangerous_reason",
    "terminal_registry",
]
