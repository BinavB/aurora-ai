"""Safe filesystem primitives: atomic writes and pre-overwrite backups.

Writes go to a temporary file in the destination directory and are then
atomically swapped into place, so a crash mid-write never leaves a truncated
file. Existing files are backed up before being overwritten.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_BACKUP_SUFFIX = ".bak"


def backup_if_exists(path: Path) -> Path | None:
    """Copy ``path`` to a sibling ``.bak`` file if it exists.

    Args:
        path: File that is about to be overwritten.

    Returns:
        The backup path, or ``None`` if the original did not exist.
    """
    if not path.exists():
        return None
    backup = path.with_name(path.name + _BACKUP_SUFFIX)
    shutil.copy2(path, backup)
    return backup


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> int:
    """Atomically write ``content`` to ``path``.

    Args:
        path: Destination file (parent directories are created).
        content: Text to write.
        encoding: Text encoding.

    Returns:
        The number of bytes written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode(encoding)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return len(data)
