"""Per-task model fallback chains.

Each task kind maps to an ordered list of ``(provider, model)`` preferences —
primary → secondary → third → local. The router tries them in order (skipping
unavailable ones); the services' failover moves to the next on any error.
"""

from __future__ import annotations

from typing import Final

from aurora.app.router.models import TaskKind

# Ordered preference per task. Providers become available once their key is set
# (local ollama is always available); unavailable links are skipped.
CHAINS: Final[dict[TaskKind, tuple[tuple[str, str], ...]]] = {
    TaskKind.CHAT: (
        ("gemini", "gemini-flash-latest"),
        ("groq", "llama-3.3-70b-versatile"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("ollama", "qwen3:8b"),
    ),
    TaskKind.PLAN: (
        ("groq", "openai/gpt-oss-120b"),  # heavy reasoning, free on Groq
        ("gemini", "gemini-flash-latest"),
        ("openrouter", "deepseek/deepseek-r1:free"),
        ("ollama", "qwen3:32b"),
    ),
    TaskKind.REVIEW: (
        ("groq", "openai/gpt-oss-120b"),
        ("groq", "qwen/qwen3-32b"),
        ("gemini", "gemini-flash-latest"),
        ("ollama", "qwen3:32b"),
    ),
    TaskKind.IMPLEMENT: (
        ("mistral", "codestral-latest"),
        ("groq", "llama-3.3-70b-versatile"),
        ("gemini", "gemini-flash-latest"),
        ("ollama", "devstral"),
    ),
    TaskKind.SUMMARIZE: (
        ("gemini", "gemini-flash-latest"),
        ("groq", "llama-3.3-70b-versatile"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("ollama", "qwen3:8b"),
    ),
    TaskKind.EXPLAIN: (
        ("groq", "openai/gpt-oss-120b"),
        ("gemini", "gemini-flash-latest"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("ollama", "qwen3:8b"),
    ),
}
