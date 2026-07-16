"""Path sandboxing: normalize paths and prevent directory traversal.

All filesystem tools resolve caller-supplied paths through a
:class:`PathSandbox` bound to a root directory. Absolute paths and ``..``
escapes are rejected, satisfying the architecture's path-safety rules on every
platform.
"""

from __future__ import annotations

from pathlib import Path, PurePath

from aurora.app.core.exceptions import ValidationError


class PathSandbox:
    """Resolves relative paths within a fixed root, rejecting escapes."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        """The absolute sandbox root."""
        return self._root

    def resolve(self, relative: str) -> Path:
        """Resolve ``relative`` against the root.

        Args:
            relative: A path relative to the sandbox root.

        Returns:
            The absolute, normalized path inside the sandbox.

        Raises:
            ValidationError: If the path is absolute or escapes the root.
        """
        if not relative or PurePath(relative).is_absolute():
            raise ValidationError(
                "Path must be relative and non-empty",
                details={"path": relative},
            )
        candidate = (self._root / relative).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise ValidationError(
                "Path escapes the sandbox root",
                details={"path": relative},
            )
        return candidate

    def relative(self, path: Path) -> str:
        """Return ``path`` expressed relative to the root, using ``/``."""
        return path.relative_to(self._root).as_posix()
