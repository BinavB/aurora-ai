"""The Router: select a provider/model and tool/context guidance.

Routing is pure policy over model metadata — no provider-specific code lives
here. Decisions consider availability, offline mode, required capabilities,
cost, latency, and user preference.
"""

from __future__ import annotations

from aurora.app.core.exceptions import RouterError
from aurora.app.core.logging import get_logger
from aurora.app.router.catalog import ModelCatalog
from aurora.app.router.chains import CHAINS
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

    def reload(self, catalog: ModelCatalog) -> None:
        """Replace the model catalog (e.g. after credentials change)."""
        self._catalog = catalog

    def route(self, request: RoutingRequest) -> RoutingDecision:
        """Choose the single best model and return a structured decision.

        Raises:
            RouterError: If no available model satisfies the constraints.
        """
        ranked = self.rank(request)
        if not ranked:
            raise RouterError(
                "No available model satisfies the routing constraints",
                details={"offline": request.offline, "task": request.task},
            )
        _logger.info(
            "route", extra={"provider": ranked[0].provider, "model": ranked[0].model}
        )
        return ranked[0]

    def rank(self, request: RoutingRequest) -> list[RoutingDecision]:
        """Return viable models in this task's fallback-chain order.

        Chain links that are unavailable are skipped; any remaining available
        models are appended as a catch-all so a request never dead-ends while
        an alternative exists.
        """
        available = self._filter(request)
        by_key = {(m.provider, m.model): m for m in available}
        ordered: list[ModelProfile] = []
        seen: set[tuple[str, str]] = set()

        for provider, model in CHAINS.get(request.kind, ()):
            profile = by_key.get((provider, model))
            if profile is not None and (provider, model) not in seen:
                ordered.append(profile)
                seen.add((provider, model))

        for profile in sorted(
            available, key=lambda m: (m.cost_per_1k, m.latency_ms, m.model)
        ):
            key = (profile.provider, profile.model)
            if key not in seen:
                ordered.append(profile)
                seen.add(key)

        if request.prefer_model or request.prefer_provider:
            ordered.sort(key=lambda m: 0 if self._is_preferred(m, request) else 1)

        return [self._to_decision(profile, request) for profile in ordered]

    @staticmethod
    def _is_preferred(model: ModelProfile, request: RoutingRequest) -> bool:
        if request.prefer_model:
            return model.model == request.prefer_model
        return model.provider == request.prefer_provider

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

    def _to_decision(
        self, profile: ModelProfile, request: RoutingRequest
    ) -> RoutingDecision:
        if self._is_preferred(profile, request):
            reason = "user-preferred model"
        else:
            reason = f"{request.kind.value} chain"
        return RoutingDecision(
            provider=profile.provider,
            model=profile.model,
            reason=reason,
            estimated_cost_per_1k=profile.cost_per_1k,
            tools=self._tools_for(request),
            context_max_tokens=self._context_tokens(request, profile),
        )

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
