# Milestone 7 — Router

Status: **complete**, awaiting acceptance.

Implements the architecture's **Router**: decide provider, model, tools, and
context. Pure policy over model metadata — no provider-specific code.

## Delivered

| Module | Responsibility |
| --- | --- |
| `models.py` | `Capability`, `ModelProfile`, `RoutingRequest`, `RoutingDecision`. |
| `catalog.py` | `ModelCatalog` + `build_catalog(settings)` (availability from config). |
| `router.py` | `Router.route()` — filtering + ranking policy. |

## Routing decision factors (per spec)

- **Availability** — a model is available if it is local or its provider has a
  configured API key (`build_catalog` derives this from settings).
- **Offline mode** — restricts the pool to local models.
- **Model capability** — filters by required capabilities; `needs_tools` and
  `long_context` add `TOOLS` / `LONG_CONTEXT` requirements.
- **Cost** — optional `max_cost_per_1k` cap; ranking prefers lower cost.
- **Latency** — tie-breaker after cost.
- **User preference** — an exact `prefer_model` wins outright; `prefer_provider`
  is favored in ranking.

The decision also returns **which tools** (`filesystem`, plus `terminal`/`git`
when tools are needed) and **which context budget** (`context_max_tokens`,
8000 for long-context-capable models else 2000).

## Design notes

- Provider-independent: the router imports no provider module; it reasons over
  `ModelProfile` metadata only.
- Sensible default policy: a free, capable local model wins on cost/latency;
  cloud models are selected when a required capability (tools, vision, long
  context, reasoning) rules the local model out, or on explicit preference.
- No candidate → structured `RouterError`.

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 11 new (143 total) | ✓ this file | ✓ logs route | ✓ `RouterError` | ✓ strict | ✓ Ruff + Black | ✓ no provider-specific code |

## Next milestone (not started)

**Agents** (`app/agents`) — Planner, Coder, Reviewer, Executor, Conversation,
Context Builder. Each performs one task, communicates only through interfaces,
and never calls external APIs directly (they go through providers/tools).
