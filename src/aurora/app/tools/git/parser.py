"""Parsing helpers for git porcelain output."""

from __future__ import annotations

from aurora.app.tools.git.models import StatusEntry


def parse_status(porcelain: str) -> list[StatusEntry]:
    """Parse ``git status --porcelain`` output into structured entries.

    Args:
        porcelain: Raw output of ``git status --porcelain``.

    Returns:
        One :class:`StatusEntry` per changed path. For renames, the
        destination path is reported.
    """
    entries: list[StatusEntry] = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        # Porcelain v1: two status chars, a space, then the path.
        code = line[:2]
        remainder = line[3:]
        path = remainder.split(" -> ")[-1] if " -> " in remainder else remainder
        entries.append(StatusEntry(code=code, path=path))
    return entries
