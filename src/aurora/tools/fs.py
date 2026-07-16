"""Filesystem tools, sandboxed to a root directory.

Every path argument is resolved and checked to lie within the configured root,
so a tool can never read or write outside its sandbox (including via ``..`` or
absolute paths).
"""

from __future__ import annotations

from pathlib import Path

from aurora.tools.base import BaseTool, ToolResult

_STRING = {"type": "string"}


class _Sandboxed(BaseTool):
    """Base for tools operating under a fixed root directory."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        super().__init__()

    def _resolve(self, relative: str) -> Path:
        """Resolve ``relative`` against the root, rejecting escapes."""
        candidate = (self._root / relative).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise ValueError(f"Path '{relative}' escapes the sandbox root")
        return candidate


class ReadFileTool(_Sandboxed):
    name = "read_file"
    description = "Read a UTF-8 text file within the sandbox root."
    parameters = {
        "type": "object",
        "properties": {"path": _STRING},
        "required": ["path"],
    }

    async def run(self, **kwargs: object) -> ToolResult:
        try:
            target = self._resolve(str(kwargs["path"]))
            return ToolResult(ok=True, output=target.read_text(encoding="utf-8"))
        except (KeyError, OSError, ValueError) as exc:
            return ToolResult(ok=False, output=str(exc))


class WriteFileTool(_Sandboxed):
    name = "write_file"
    description = "Write UTF-8 text to a file within the sandbox root, creating parents."
    parameters = {
        "type": "object",
        "properties": {"path": _STRING, "content": _STRING},
        "required": ["path", "content"],
    }

    async def run(self, **kwargs: object) -> ToolResult:
        try:
            target = self._resolve(str(kwargs["path"]))
            target.parent.mkdir(parents=True, exist_ok=True)
            content = str(kwargs["content"])
            target.write_text(content, encoding="utf-8")
            return ToolResult(ok=True, output=f"Wrote {len(content)} chars to {target.name}")
        except (KeyError, OSError, ValueError) as exc:
            return ToolResult(ok=False, output=str(exc))


class ListDirTool(_Sandboxed):
    name = "list_dir"
    description = "List entries of a directory within the sandbox root."
    parameters = {
        "type": "object",
        "properties": {"path": _STRING},
        "required": [],
    }

    async def run(self, **kwargs: object) -> ToolResult:
        try:
            target = self._resolve(str(kwargs.get("path", ".")))
            if not target.is_dir():
                return ToolResult(ok=False, output=f"Not a directory: {target.name}")
            entries = sorted(
                f"{p.name}/" if p.is_dir() else p.name for p in target.iterdir()
            )
            return ToolResult(ok=True, output="\n".join(entries))
        except (OSError, ValueError) as exc:
            return ToolResult(ok=False, output=str(exc))
