# Milestone 9 — Services

Status: **complete**, awaiting acceptance.

Implements the architecture's **Services** layer: coordinate business logic
across `API → Services → Agents → Tools → Providers`.

## Delivered

| Module | Service | Use case |
| --- | --- | --- |
| `factory.py` | `ProviderFactory` / `DefaultProviderFactory` | Turn a routed provider *name* into a live provider. |
| `chat_service.py` | `ChatService` | Route → converse → persist a chat turn. |
| `planning_service.py` | `PlanningService` | Build context → produce a plan. |
| `review_service.py` | `ReviewService` | Route → review code. |
| `implementation_service.py` | `ImplementationService` | Context → generate code → (on approval) write via tools. |

Supporting: `base.py` (`RoutedService` — router-driven provider acquisition with
guaranteed cleanup) and `models.py` (result models).

## Coordination flow

Each service: builds a `RoutingRequest` → asks the **Router** for a
provider/model → obtains the provider from the **ProviderFactory** → drives the
relevant **Agents** (which use **Tools** and **Providers**) → returns a typed
result. The provider is always closed via an async context manager.

## Architecture compliance

- **Services coordinate, agents do the work** — no low-level logic lives in
  services; they wire router + factory + context + memory + agents.
- **Dependency direction preserved** — `services → agents → tools → providers`,
  plus `services → router / context` (all downward).
- **Approval gating** — `ImplementationService` performs a **dry run by
  default** (returns proposed content, writes nothing); it applies changes
  through the executor/tools only when `approve=True`.
- **Provider lifecycle** — acquired per request and always released (verified
  the provider is closed even on the happy path).

## Verified behaviour

Chat routes to the free local model, persists the turn, and closes the
provider; planning builds context (surfacing the relevant file) and returns
parsed steps; review returns findings + summary; implementation writes nothing
on a dry run and writes the generated file on approval; a tools-requiring task
selects a tool-capable model.

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 7 new (157 total) | ✓ this file | ✓ via lower layers | ✓ structured (propagated) | ✓ strict | ✓ Ruff + Black | ✓ correct layering |

## Next milestone (not started)

**API** (`app/api`) — FastAPI surface (REST, streaming, WebSockets) that only
orchestrates: thin endpoints delegating to services, structured error
responses, no business logic.
