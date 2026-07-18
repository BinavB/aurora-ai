"""Concrete filesystem tools.

Each tool is sandboxed to a root via :class:`PathSandbox` and returns
structured output. Writes are atomic and back up any file they overwrite.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from aurora.app.core.exceptions import ToolError
from aurora.app.tools.base import BaseTool
from aurora.app.tools.filesystem.io import atomic_write_text, backup_if_exists
from aurora.app.tools.filesystem.models import (
    DeleteFileOutput,
    PathInput,
    ReadFileOutput,
    RenameFileInput,
    RenameFileOutput,
    RepoMapEntry,
    RepoMapInput,
    RepoMapOutput,
    SearchInput,
    SearchMatch,
    SearchOutput,
    WriteFileInput,
    WriteFileOutput,
)
from aurora.app.tools.filesystem.paths import PathSandbox
from aurora.app.tools.models import Permission, ToolMetadata

_CATEGORY = "filesystem"

# Directories and files that are noise or secrets — never surfaced in search
# results (so they never reach a plan's context or an LLM prompt).
_IGNORED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
        "dist",
        "build",
    }
)


def _is_ignored(path: Path, root: Path) -> bool:
    """True for VCS internals, caches, and secret ``.env`` files."""
    parts = path.relative_to(root).parts
    if any(part in _IGNORED_DIRS for part in parts):
        return True
    name = path.name
    if name == ".env" or (
        name.startswith(".env.") and not name.endswith((".example", ".sample"))
    ):
        return True
    return False


_SOURCE_EXTS = frozenset({".py", ".js", ".ts", ".jsx", ".tsx"})
_MAX_SYMBOLS_PER_FILE = 40
_JS_SYMBOL = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?"
    r"(?:(function|class)\s+([A-Za-z_$][\w$]*)"
    r"|const\s+([A-Za-z_$][\w$]*)\s*=)",
    re.MULTILINE,
)


def _python_symbols(content: str) -> list[str]:
    """Top-level function/class signatures via the ``ast`` module."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(f"class {node.name}")
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            kw = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            args = ", ".join(arg.arg for arg in node.args.args)
            symbols.append(f"{kw} {node.name}({args})")
    return symbols


def _js_symbols(content: str) -> list[str]:
    """Top-level function/class/const declarations via a light regex."""
    symbols: list[str] = []
    for match in _JS_SYMBOL.finditer(content):
        keyword, named, const = match.group(1), match.group(2), match.group(3)
        if named:
            symbols.append(f"{keyword} {named}")
        elif const:
            symbols.append(f"const {const}")
    return symbols


def _symbols_for(suffix: str, content: str) -> list[str]:
    extractor = _python_symbols if suffix == ".py" else _js_symbols
    return extractor(content)[:_MAX_SYMBOLS_PER_FILE]


class _FsTool(BaseTool):
    """Base for filesystem tools sharing a sandbox."""

    def __init__(self, root: str | Path) -> None:
        self._sandbox = PathSandbox(root)
        super().__init__()


class ReadFileTool(_FsTool):
    """Read a UTF-8 text file within the sandbox."""

    metadata = ToolMetadata(
        name="read_file",
        description="Read a UTF-8 text file within the project root.",
        category=_CATEGORY,
        permissions=frozenset({Permission.READ}),
    )
    input_model = PathInput
    output_model = ReadFileOutput

    async def execute(self, payload: PathInput) -> ReadFileOutput:
        target = self._sandbox.resolve(payload.path)
        try:
            content = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise ToolError(f"Cannot read '{payload.path}': {exc}") from exc
        return ReadFileOutput(
            path=self._sandbox.relative(target),
            content=content,
            size_bytes=len(content.encode("utf-8")),
        )


class WriteFileTool(_FsTool):
    """Atomically write a UTF-8 text file, backing up any existing file."""

    metadata = ToolMetadata(
        name="write_file",
        description="Atomically write a UTF-8 text file within the project root.",
        category=_CATEGORY,
        permissions=frozenset({Permission.WRITE}),
    )
    input_model = WriteFileInput
    output_model = WriteFileOutput

    async def execute(self, payload: WriteFileInput) -> WriteFileOutput:
        target = self._sandbox.resolve(payload.path)
        if target.exists() and not payload.overwrite:
            raise ToolError(
                f"File '{payload.path}' exists and overwrite is disabled",
                details={"path": payload.path},
            )
        try:
            backup = backup_if_exists(target)
            written = atomic_write_text(target, payload.content)
        except OSError as exc:
            raise ToolError(f"Cannot write '{payload.path}': {exc}") from exc
        return WriteFileOutput(
            path=self._sandbox.relative(target),
            bytes_written=written,
            backup=self._sandbox.relative(backup) if backup else None,
        )


class DeleteFileTool(_FsTool):
    """Delete a file within the sandbox."""

    metadata = ToolMetadata(
        name="delete_file",
        description="Delete a file within the project root.",
        category=_CATEGORY,
        permissions=frozenset({Permission.DELETE}),
    )
    input_model = PathInput
    output_model = DeleteFileOutput

    async def execute(self, payload: PathInput) -> DeleteFileOutput:
        target = self._sandbox.resolve(payload.path)
        if not target.is_file():
            raise ToolError(
                f"No such file '{payload.path}'", details={"path": payload.path}
            )
        try:
            target.unlink()
        except OSError as exc:
            raise ToolError(f"Cannot delete '{payload.path}': {exc}") from exc
        return DeleteFileOutput(path=self._sandbox.relative(target), deleted=True)


class RenameFileTool(_FsTool):
    """Rename or move a file within the sandbox."""

    metadata = ToolMetadata(
        name="rename_file",
        description="Rename or move a file within the project root.",
        category=_CATEGORY,
        permissions=frozenset({Permission.WRITE}),
    )
    input_model = RenameFileInput
    output_model = RenameFileOutput

    async def execute(self, payload: RenameFileInput) -> RenameFileOutput:
        src = self._sandbox.resolve(payload.src)
        dst = self._sandbox.resolve(payload.dst)
        if not src.exists():
            raise ToolError(f"No such file '{payload.src}'")
        if dst.exists():
            raise ToolError(f"Destination '{payload.dst}' already exists")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
        except OSError as exc:
            raise ToolError(f"Cannot rename '{payload.src}': {exc}") from exc
        return RenameFileOutput(
            src=self._sandbox.relative(src), dst=self._sandbox.relative(dst)
        )


class SearchProjectTool(_FsTool):
    """Search text file contents within the sandbox for a substring."""

    metadata = ToolMetadata(
        name="search_project",
        description="Search text files within the project root for a substring.",
        category=_CATEGORY,
        permissions=frozenset({Permission.READ}),
    )
    input_model = SearchInput
    output_model = SearchOutput

    async def execute(self, payload: SearchInput) -> SearchOutput:
        matches: list[SearchMatch] = []
        truncated = False
        root = self._sandbox.root
        for path in sorted(root.glob(payload.glob)):
            if not path.is_file() or _is_ignored(path, root):
                continue
            if self._scan(path, payload.query, payload.max_results, matches):
                truncated = True
                break
        return SearchOutput(matches=matches, count=len(matches), truncated=truncated)

    def _scan(
        self, path: Path, query: str, limit: int, matches: list[SearchMatch]
    ) -> bool:
        """Append matches from ``path``; return True if ``limit`` was hit."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False  # skip binary/unreadable files
        rel = self._sandbox.relative(path)
        for number, line in enumerate(text.splitlines(), start=1):
            if query in line:
                matches.append(SearchMatch(path=rel, line=number, text=line.strip()))
                if len(matches) >= limit:
                    return True
        return False


class RepoMapTool(_FsTool):
    """Summarize the project: source files and their top-level symbols.

    An Aider-style repository map gives an agent a whole-project overview
    (files plus their functions/classes) so it can orient itself in an
    unfamiliar codebase without reading every file.
    """

    metadata = ToolMetadata(
        name="repo_map",
        description=(
            "Map the project: list source files and their top-level "
            "functions/classes for a quick structural overview."
        ),
        category=_CATEGORY,
        permissions=frozenset({Permission.READ}),
    )
    input_model = RepoMapInput
    output_model = RepoMapOutput

    async def execute(self, payload: RepoMapInput) -> RepoMapOutput:
        root = self._sandbox.root
        entries: list[RepoMapEntry] = []
        truncated = False
        for path in sorted(root.glob(payload.glob)):
            if not path.is_file() or _is_ignored(path, root):
                continue
            if path.suffix not in _SOURCE_EXTS:
                continue
            if len(entries) >= payload.max_files:
                truncated = True
                break
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            entries.append(
                RepoMapEntry(
                    path=self._sandbox.relative(path),
                    symbols=_symbols_for(path.suffix, content),
                )
            )
        return RepoMapOutput(
            entries=entries,
            rendered=self._render(entries),
            file_count=len(entries),
            truncated=truncated,
        )

    @staticmethod
    def _render(entries: list[RepoMapEntry]) -> str:
        lines: list[str] = []
        for entry in entries:
            lines.append(entry.path)
            lines.extend(f"    {symbol}" for symbol in entry.symbols)
        return "\n".join(lines)
