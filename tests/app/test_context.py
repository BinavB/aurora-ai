"""Tests for the context engine pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from aurora.app.context import ContextEngine, ContextRequest
from aurora.app.context.analyzer import KeywordQueryAnalyzer
from aurora.app.context.compressor import SymbolAwareCompressor
from aurora.app.context.embeddings import HashingEmbedder, cosine
from aurora.app.context.extractor import PythonSymbolExtractor
from aurora.app.context.interfaces import FileLocator
from aurora.app.context.models import FileCandidate, QueryPlan
from aurora.app.context.semantic_locator import SemanticFileLocator
from aurora.app.context.vector_index import VectorIndex
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


# --- semantic retrieval ---------------------------------------------------


def test_embedder_is_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder(dim=256)
    first = embedder.embed("issue a token for the user")
    second = embedder.embed("issue a token for the user")
    assert first == second  # stable across calls (no per-run hash salt)
    assert len(first) == 256
    assert cosine(first, second) == pytest.approx(1.0)


def test_embedder_captures_morphological_similarity() -> None:
    embedder = HashingEmbedder()
    token = embedder.embed("token")
    # Shared subword n-grams make an inflected form closer than an unrelated one.
    assert cosine(token, embedder.embed("tokens")) > cosine(
        token, embedder.embed("matrix")
    )


def test_embedder_zero_vector_for_empty_text() -> None:
    assert cosine(HashingEmbedder().embed(""), HashingEmbedder().embed("")) == 0.0


def test_vector_index_returns_nearest_first() -> None:
    embedder = HashingEmbedder()
    index = VectorIndex()
    index.add("auth", embedder.embed("authenticate a user login password"))
    index.add("math", embedder.embed("matrix multiply arithmetic sum"))
    ranked = index.query(embedder.embed("verify the user's login credentials"), k=2)
    assert [doc_id for doc_id, _ in ranked] == ["auth", "math"]
    assert ranked[0][1] > ranked[1][1]


def test_vector_index_empty_or_zero_k() -> None:
    index = VectorIndex()
    assert index.query([0.1, 0.2], k=3) == []
    index.add("a", [1.0, 0.0])
    assert index.query([1.0, 0.0], k=0) == []


class _FixedLocator(FileLocator):
    """Recall stub: returns a fixed pool with identical scores."""

    def __init__(self, paths: list[str]) -> None:
        self._paths = paths

    async def locate(self, plan: QueryPlan, max_files: int) -> list[FileCandidate]:
        return [FileCandidate(path=p, score=1.0) for p in self._paths]


async def test_semantic_locator_reranks_equal_recall(tmp_path: Path) -> None:
    # Two files a keyword pass scores identically; semantics must order them.
    (tmp_path / "auth.py").write_text(
        "def login(user, password):\n"
        "    # verify credentials and authenticate the user session\n"
        "    return authenticate(user, password)\n",
        encoding="utf-8",
    )
    (tmp_path / "math_utils.py").write_text(
        "def add(a, b):\n    # arithmetic sum of two numbers\n    return a + b\n",
        encoding="utf-8",
    )
    locator = SemanticFileLocator(
        filesystem_registry(str(tmp_path)),
        recall=_FixedLocator(["math_utils.py", "auth.py"]),
    )
    plan = QueryPlan(
        query="authenticate a user login with a password credential",
        terms=["authenticate", "user", "login", "password", "credential"],
    )
    ranked = await locator.locate(plan, max_files=2)
    assert [c.path for c in ranked] == ["auth.py", "math_utils.py"]


async def test_semantic_locator_empty_pool(tmp_path: Path) -> None:
    locator = SemanticFileLocator(
        filesystem_registry(str(tmp_path)), recall=_FixedLocator([])
    )
    plan = QueryPlan(query="anything", terms=["anything"])
    assert await locator.locate(plan, max_files=5) == []
