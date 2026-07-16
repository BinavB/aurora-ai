"""Tests for the context engine pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora.app.context import ContextEngine, ContextRequest
from aurora.app.context.analyzer import KeywordQueryAnalyzer
from aurora.app.context.compressor import SymbolAwareCompressor
from aurora.app.context.extractor import PythonSymbolExtractor
from aurora.app.context.models import QueryPlan
from aurora.app.core.types import Role
from aurora.app.tools.filesystem import filesystem_registry


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "auth.py").write_text(
        "class TokenManager:\n"
        "    def issue_token(self, user):\n"
        "        return 'token'\n",
        encoding="utf-8",
    )
    (tmp_path / "billing.py").write_text(
        "def charge(amount):\n    return amount\n", encoding="utf-8"
    )
    return tmp_path


# --- individual stages ----------------------------------------------------


def test_analyzer_drops_stopwords_and_dedupes() -> None:
    plan = KeywordQueryAnalyzer().analyze("How do I add the token token manager?")
    assert "token" in plan.terms and "manager" in plan.terms
    assert "the" not in plan.terms
    assert plan.terms.count("token") == 1


def test_extractor_reads_python_symbols() -> None:
    source = "class A:\n    pass\n\nasync def run(x, y):\n    return x\n"
    symbols = PythonSymbolExtractor().extract("m.py", source)
    kinds = {(s.name, s.kind) for s in symbols}
    assert ("A", "class") in kinds
    assert ("run", "function") in kinds
    run = next(s for s in symbols if s.name == "run")
    assert run.signature == "async def run(x, y)"


def test_extractor_ignores_non_python() -> None:
    assert PythonSymbolExtractor().extract("notes.txt", "class A: pass") == []


def test_compressor_respects_budget() -> None:
    plan = QueryPlan(query="token", terms=["token"])
    big = "token line\n" * 1000
    chunk = SymbolAwareCompressor().compress(plan, "a.py", big, [], budget_tokens=20)
    assert 0 < chunk.tokens <= 20


# --- full pipeline --------------------------------------------------------


async def test_pipeline_locates_and_builds_context(project: Path) -> None:
    engine = ContextEngine(filesystem_registry(str(project)))
    built = await engine.build(ContextRequest(query="issue a token for the manager"))

    assert "auth.py" in built.files_used
    # The most relevant file (auth.py) should lead the file list.
    assert built.files_used[0] == "auth.py"
    # Messages: system prompt, context block, user query.
    assert built.messages[0].role is Role.SYSTEM
    assert built.messages[-1].role is Role.USER
    assert "TokenManager" in built.messages[1].content
    assert built.token_estimate > 0


async def test_pipeline_truncates_under_tight_budget(project: Path) -> None:
    engine = ContextEngine(filesystem_registry(str(project)))
    built = await engine.build(ContextRequest(query="token manager charge", max_tokens=5))
    assert built.truncated is True


async def test_pipeline_handles_no_matches(project: Path) -> None:
    engine = ContextEngine(filesystem_registry(str(project)))
    built = await engine.build(ContextRequest(query="nonexistentsymbol"))
    assert built.files_used == []
    # Still returns a valid prompt (system + user), just no context block.
    assert [m.role for m in built.messages] == [Role.SYSTEM, Role.USER]
