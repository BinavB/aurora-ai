"""The Router: select a provider/model and tool/context guidance.

Routing is pure policy over model metadata — no provider-specific code lives
here. Decisions consider availability, offline mode, required capabilities,
cost, latency, and user preference.
"""

from __future__ import annotations

from aurora.app.core.exceptions import RouterError
from aurora.app.core.logging import get_logger
from aurora.app.router.catalog import ModelCatalog
from aurora.app.router.models import (
    Capability,
    ModelProfile,
    RoutingDecision,
    RoutingRequest,
)

_logger = get_logger("router")

_SHORT_CONTEXT = 2000
_LONG_CONTEXT = 8000


class Router:
    """Selects the best model for a routing request."""

    def __init__(self, catalog: ModelCatalog) -> None:
        self._catalog = catalog

    def route(self, request: RoutingRequest) -> RoutingDecision:
        """Choose a model and return a structured decision.

        Raises:
            RouterError: If no available model satisfies the constraints.
        """
        pool = self._filter(request)
        if not pool:
            raise RouterError(
                "No available model satisfies the routing constraints",
                details={"offline": request.offline, "task": request.task},
            )
        profile, reason = self._select(pool, request)
        decision = RoutingDecision(
            provider=profile.provider,
            model=profile.model,
            reason=reason,
            estimated_cost_per_1k=profile.cost_per_1k,
            tools=self._tools_for(request),
            context_max_tokens=self._context_tokens(request, profile),
        )
        _logger.info(
            "route",
            extra={"provider": profile.provider, "model": profile.model},
        )
        return decision

    def _required_capabilities(self, request: RoutingRequest) -> set[Capability]:
        caps = set(request.required_capabilities)
        if request.needs_tools:
            caps.add(Capability.TOOLS)
        if request.long_context:
            caps.add(Capability.LONG_CONTEXT)
        return caps

    def _filter(self, request: RoutingRequest) -> list[ModelProfile]:
        pool = self._catalog.available()
        if request.offline:
            pool = [m for m in pool if m.is_local]
        caps = self._required_capabilities(request)
        pool = [m for m in pool if caps <= m.capabilities]
        if request.max_cost_per_1k is not None:
            pool = [m for m in pool if m.cost_per_1k <= request.max_cost_per_1k]
        return pool

    def _select(
        self, pool: list[ModelProfile], request: RoutingRequest
    ) -> tuple[ModelProfile, str]:
        if request.prefer_model:
            for model in pool:
                if model.model == request.prefer_model and (
                    not request.prefer_provider
                    or model.provider == request.prefer_provider
                ):
                    return model, "explicit model preference"

        def sort_key(model: ModelProfile) -> tuple[int, float, int, str]:
            prefers_provider = (
                request.prefer_provider is not None
                and model.provider == request.prefer_provider
            )
            return (
                0 if prefers_provider else 1,
                model.cost_per_1k,
                model.latency_ms,
                model.model,
            )

        best = min(pool, key=sort_key)
        if request.prefer_provider and best.provider == request.prefer_provider:
            return best, "preferred provider, lowest cost"
        return best, "lowest cost among capable available models"

    @staticmethod
    def _tools_for(request: RoutingRequest) -> list[str]:
        tools = ["filesystem"]
        if request.needs_tools:
            tools.extend(["terminal", "git"])
        return tools

    @staticmethod
    def _context_tokens(request: RoutingRequest, profile: ModelProfile) -> int:
        if request.long_context and Capability.LONG_CONTEXT in profile.capabilities:
            return _LONG_CONTEXT
        return _SHORT_CONTEXT
