"""Structured multi-agent collaboration with a user-controlled effort dial.

A fast **dispatcher** agent decides the assignment (how many specialists and
what each focuses on) for the chosen effort level. Specialists then work **in
parallel** (fan-out) and a single **synthesizer** merges their drafts (fan-in) —
a one-pass DAG with no agent-to-agent chatter and no loops.

Effort:
    fast     — one fastest agent, minimal latency.
    balanced — dispatcher picks 2 specialists + a synthesizer.
    max      — dispatcher picks 3 powerful specialists + a synthesizer.
"""

from __future__ import annotations

import asyncio
import re
from enum import StrEnum

from pydantic import BaseModel, Field

from aurora.app.agents.llm import system, user
from aurora.app.core.logging import get_logger
from aurora.app.router.models import RoutingRequest, TaskKind
from aurora.app.router.router import Router
from aurora.app.search import WebSearch, gather_web_context, prompt_with_web
from aurora.app.search.tavily import SearchResult
from aurora.app.services.base import RoutedService
from aurora.app.services.factory import ProviderFactory

_logger = get_logger("services.collab")


class Effort(StrEnum):
    """How much thinking/collaboration the user wants."""

    FAST = "fast"
    BALANCED = "balanced"
    MAX = "max"


# Fallback specialist focuses per task, used if the dispatcher can't be parsed.
_DEFAULT_FOCUSES: dict[TaskKind, tuple[str, ...]] = {
    TaskKind.CHAT: ("accuracy", "clarity", "completeness"),
    TaskKind.SUMMARIZE: ("key points", "brevity", "structure"),
    TaskKind.EXPLAIN: ("core concept", "intuition", "example"),
    TaskKind.PLAN: ("architecture", "scalability", "risks"),
    TaskKind.REVIEW: ("correctness", "performance", "maintainability"),
    TaskKind.IMPLEMENT: ("requirements", "implementation", "edge cases"),
}

# effort -> (specialist count, use synthesizer, per-draft token cap, synth cap)
_PLAN: dict[Effort, tuple[int, bool, int, int]] = {
    Effort.FAST: (1, False, 600, 0),
    Effort.BALANCED: (2, True, 700, 1500),
    Effort.MAX: (3, True, 1100, 2200),
}


_STYLE_PREFIX = re.compile(r"^\[Style:[^\]]*\]\s*")
_DEEP_TOPIC = re.compile(
    r"\b(architecture|design (a|an|the)|trade-?offs?|in[- ]depth|detailed|deep dive|"
    r"roadmap|strategy|refactor|research|migration)\b",
    re.IGNORECASE,
)
_MEDIUM_TOPIC = re.compile(
    r"\b(explain|compare|difference|pros and cons|why|how (do|does|to|can|would)|"
    r"summari[sz]e|review|plan|write|essay|steps)\b",
    re.IGNORECASE,
)
_SMALL_WORD_LIMIT = 12
_LARGE_WORD_LIMIT = 80


def recommend_effort(message: str) -> Effort:
    text = _STYLE_PREFIX.sub("", message).strip()
    words = len(text.split())
    if "```" in text or words > _LARGE_WORD_LIMIT or _DEEP_TOPIC.search(text):
        return Effort.MAX
    if words <= _SMALL_WORD_LIMIT and not _MEDIUM_TOPIC.search(text):
        return Effort.FAST
    return Effort.BALANCED


class CollabResult(BaseModel):
    """The synthesized output plus the roster of engines that collaborated."""

    content: str
    roster: list[str]
    sources: list[SearchResult] = Field(default_factory=list)
    effort_used: str = Effort.BALANCED.value
    recommended_effort: str | None = None


class CollaborationService(RoutedService):
    """Run a task through an effort-scaled team of specialists."""

    def __init__(
        self,
        router: Router,
        factory: ProviderFactory,
        search: WebSearch | None = None,
    ) -> None:
        super().__init__(router, factory)
        self._search = search

    async def collaborate(
        self,
        kind: TaskKind,
        task: str,
        effort: Effort = Effort.BALANCED,
        context: list | None = None,
    ) -> CollabResult:
        """Dispatch specialists per ``effort``, run in parallel, synthesize."""
        context = context or []
        recommended = recommend_effort(task) if kind is TaskKind.CHAT else None
        if recommended is Effort.FAST:
            effort = Effort.FAST
        count, use_synth, draft_cap, synth_cap = _PLAN[effort]
        suggestion = recommended.value if recommended else None
        web = await gather_web_context(self._search, task)

        # Fast: a single, fastest agent — no dispatcher, no synthesis.
        if effort is Effort.FAST:
            decision, text = await self._complete(
                RoutingRequest(task=task, kind=TaskKind.CHAT),
                [
                    system(
                        prompt_with_web(
                            "Answer briefly and clearly. Use one or two sentences "
                            "when the question is simple.",
                            web,
                        )
                    ),
                    *context,
                    user(task),
                ],
                max_tokens=draft_cap,
            )
            return CollabResult(
                content=text,
                roster=[f"Solo · {decision.provider}/{decision.model}"],
                sources=web.sources,
                effort_used=effort.value,
                recommended_effort=suggestion,
            )

        # A fast, logical dispatcher assigns the specialist focuses.
        focuses, dispatch_engine = await self._assign(kind, task, count)
        roster = [f"Dispatcher · {dispatch_engine}"]

        async def draft(focus: str) -> tuple[str, str, str]:
            prompt = (
                f"You are the '{focus}' specialist. Contribute only your angle. "
                "Be concise: at most ~8 short bullet points."
            )
            decision, text = await self._complete(
                RoutingRequest(task=task, kind=kind),
                [system(prompt_with_web(prompt, web)), *context, user(task)],
                max_tokens=draft_cap,
            )
            return focus, f"{decision.provider}/{decision.model}", text

        drafted = await asyncio.gather(
            *(draft(f) for f in focuses), return_exceptions=True
        )
        good = [d for d in drafted if not isinstance(d, BaseException)]
        if not good:
            raise next(d for d in drafted if isinstance(d, BaseException))
        roster += [f"{focus} · {engine}" for focus, engine, _ in good]

        if not use_synth:
            return CollabResult(
                content=good[0][2],
                roster=roster,
                sources=web.sources,
                effort_used=effort.value,
                recommended_effort=suggestion,
            )

        block = "\n\n".join(f"[{focus}]\n{text}" for focus, _, text in good)
        merge = (
            f"Task:\n{task}\n\nSpecialist drafts:\n{block}\n\nProduce the final result."
        )
        synth_kind = kind if effort is Effort.MAX else TaskKind.CHAT
        decision, final = await self._complete(
            RoutingRequest(task=task, kind=synth_kind),
            [
                system(
                    "Merge the specialist drafts into one cohesive result. Write in "
                    "plain, friendly language and make the answer as long as the "
                    "question needs and no longer. Avoid tables unless the user asks "
                    "for one."
                ),
                user(merge),
            ],
            max_tokens=synth_cap,
        )
        roster.append(f"Synthesizer · {decision.provider}/{decision.model}")
        return CollabResult(
            content=final,
            roster=roster,
            sources=web.sources,
            effort_used=effort.value,
            recommended_effort=suggestion,
        )

    async def _assign(
        self, kind: TaskKind, task: str, count: int
    ) -> tuple[list[str], str]:
        """Fast dispatcher: choose ``count`` specialist focuses for the task."""
        ask = (
            f"For this {kind.value} task, name exactly {count} distinct specialist "
            "focus areas (2-4 words each), comma-separated, no numbering.\n"
            f"Task: {task}"
        )
        try:
            decision, text = await self._complete(
                RoutingRequest(task=task, kind=TaskKind.CHAT),
                [system("You assign specialists. Reply with only the list."), user(ask)],
                max_tokens=60,
            )
            parts = [p.strip(" -*•\t.").strip() for p in re.split(r"[,\n]", text)]
            focuses = [p for p in parts if p and len(p) < 40][:count]
            engine = f"{decision.provider}/{decision.model}"
        except Exception:  # noqa: BLE001 - fall back to defaults on any failure
            focuses, engine = [], "fallback"
        defaults = _DEFAULT_FOCUSES.get(kind, _DEFAULT_FOCUSES[TaskKind.CHAT])
        while len(focuses) < count:
            focuses.append(defaults[len(focuses) % len(defaults)])
        return focuses[:count], engine
