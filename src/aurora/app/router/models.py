"""Routing models: capabilities, model profiles, requests, and decisions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Capability(StrEnum):
    """A capability a model may provide."""

    CHAT = "chat"
    CODE = "code"
    REASONING = "reasoning"
    VISION = "vision"
    LONG_CONTEXT = "long_context"
    TOOLS = "tools"


class TaskKind(StrEnum):
    """The kind of work a request represents, used for chain-based routing."""

    CHAT = "chat"
    PLAN = "plan"
    REVIEW = "review"
    IMPLEMENT = "implement"
    SUMMARIZE = "summarize"
    EXPLAIN = "explain"


class ModelProfile(BaseModel):
    """Static, provider-independent metadata describing a model.

    Attributes:
        provider: Provider name (matches the providers registry).
        model: Model identifier passed to the provider.
        capabilities: What the model can do.
        cost_per_1k: Blended USD cost per 1k tokens (0 for local/free models).
        is_local: Whether the model runs locally (offline-capable).
        latency_ms: Rough latency hint for ranking.
        available: Whether the model is usable given current configuration.
        strengths: Relative skill levels (0-3) keyed by skill name — e.g.
            ``{"reasoning": 3, "coding": 2}`` — used for model-aware assignment.
    """

    provider: str
    model: str
    capabilities: frozenset[Capability]
    cost_per_1k: float = Field(ge=0.0)
    is_local: bool = False
    latency_ms: int = Field(gt=0)
    available: bool = True
    strengths: dict[str, int] = Field(default_factory=dict)


class RoutingRequest(BaseModel):
    """A request to select a model for a task."""

    task: str = Field(min_length=1)
    kind: TaskKind = TaskKind.CHAT
    offline: bool = False
    needs_tools: bool = False
    long_context: bool = False
    required_capabilities: frozenset[Capability] = Field(default_factory=frozenset)
    prefer_provider: str | None = None
    prefer_model: str | None = None
    max_cost_per_1k: float | None = Field(default=None, ge=0.0)


class RoutingDecision(BaseModel):
    """The chosen provider/model plus tool and context guidance."""

    provider: str
    model: str
    reason: str
    estimated_cost_per_1k: float
    tools: list[str]
    context_max_tokens: int
