"""Default symbol extractor: parse Python files with the ``ast`` module.

Extraction operates on file *content* (a string obtained via the filesystem
tools), never by opening files directly. Non-Python files yield no symbols.
"""

from __future__ import annotations

import ast

from aurora.app.context.interfaces import SymbolExtractor
from aurora.app.context.models import Symbol


class PythonSymbolExtractor(SymbolExtractor):
    """Extract top-level functions and classes from Python source."""

    def extract(self, path: str, content: str) -> list[Symbol]:
        if not path.endswith(".py"):
            return []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        symbols: list[Symbol] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.append(
                    Symbol(
                        name=node.name,
                        kind="class",
                        line=node.lineno,
                        signature=f"class {node.name}",
                    )
                )
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                symbols.append(self._function_symbol(node))
        return symbols

    @staticmethod
    def _function_symbol(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Symbol:
        args = [arg.arg for arg in node.args.args]
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return Symbol(
            name=node.name,
            kind="function",
            line=node.lineno,
            signature=f"{prefix} {node.name}({', '.join(args)})",
        )
