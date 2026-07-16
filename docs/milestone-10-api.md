# Milestone 10 — API

Status: **complete**, awaiting acceptance.

Implements the architecture's **API** layer: a FastAPI surface (REST, streaming,
WebSocket) that only orchestrates.

## Delivered

| Module | Responsibility |
| --- | --- |
| `schemas.py` | Request bodies (`ChatBody`, `PlanBody`, `ReviewBody`, `ImplementBody`). |
| `errors.py` | `AuroraError` → structured JSON with mapped HTTP status. |
| `app.py` | `create_app()` — DI wiring, lifespan, endpoints. |
| `__main__.py` | `python -m aurora.app.api` (uvicorn entrypoint). |

## Endpoints

| Method | Path | Delegates to |
| --- | --- | --- |
| GET | `/health` | — |
| GET | `/providers` | providers registry |
| GET | `/tools` | filesystem + terminal tool specs |
| POST | `/chat` | `ChatService` |
| POST | `/chat/stream` | `ChatService` (SSE stream) |
| POST | `/plan` | `PlanningService` |
| POST | `/review` | `ReviewService` |
| POST | `/implement` | `ImplementationService` |
| WS | `/ws/chat` | `ChatService` (token stream) |

## Architecture compliance

- **No business logic in routes** — each endpoint validates input and calls one
  service; coordination lives in services.
- **REST + streaming + WebSocket** — SSE via `StreamingResponse` and a
  token-streaming WebSocket, both required by the spec.
- **Structured errors** — a single handler maps every `AuroraError` to
  `code`/`message`/`details` with the right status (400/403/404/409/502/500);
  no stack traces leak.
- **Dependency injection** — `create_app` takes settings, memory, router,
  factory, and workspace root; tests inject fakes, deployments use defaults.
- **Path safety** — `/implement` writes only within the server's configured
  workspace (the filesystem tools sandbox `target_path`).

## Verified behaviour

- Tests (FastAPI `TestClient`): health, providers, tools, chat, SSE stream,
  WebSocket token stream, plan, review, implement (dry-run then approve writes
  the file), and a structured `409 router_error`.
- **Live**: boots under uvicorn; `/health`, `/providers`, `/tools` respond and a
  no-credentials tools task returns a structured `409`.

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 9 new (166 total) | ✓ this file | ✓ startup + errors | ✓ structured handler | ✓ strict | ✓ Ruff + Black | ✓ orchestration only |

## Remaining (not started)

**Frontend** (`frontend/`) — a client for the new API. The full backend stack
(core → config → providers → tools → terminal → git → database → memory →
context → router → agents → services → api) is now complete and runs live.
