"""Dangerous-command detection.

Commands are executed as an argument vector (never through a shell), so shell
metacharacters cannot inject additional commands. This module additionally
flags intrinsically destructive commands so callers must explicitly confirm
them before they run.
"""

from __future__ import annotations

from pathlib import PurePath

# Executables that are destructive regardless of arguments.
_DANGEROUS_EXECUTABLES: frozenset[str] = frozenset(
    {
        "rm",
        "rmdir",
        "del",
        "dd",
        "mkfs",
        "fdisk",
        "format",
        "shutdown",
        "reboot",
        "halt",
        "poweroff",
    }
)

# Substrings that indicate a destructive intent anywhere in the command.
_DANGEROUS_FRAGMENTS: tuple[str, ...] = (":(){", "/dev/sd", "> /dev/", ">/dev/")


def dangerous_reason(command: list[str]) -> str | None:
    """Return a reason string if ``command`` is dangerous, else ``None``.

    Args:
        command: The argument vector to inspect.

    Returns:
        A human-readable reason when the command is destructive, otherwise
        ``None``.
    """
    if not command:
        return None
    executable = PurePath(command[0]).name.lower()
    if executable in _DANGEROUS_EXECUTABLES:
        return f"'{executable}' is a destructive command"
    joined = " ".join(command)
    for fragment in _DANGEROUS_FRAGMENTS:
        if fragment in joined:
            return f"command contains a dangerous pattern: {fragment!r}"
    return None
