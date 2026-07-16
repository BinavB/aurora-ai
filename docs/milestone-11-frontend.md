# Milestone 11 — Frontend

Status: **complete**, awaiting acceptance. This completes the AEGIS project
structure.

## Delivered

| File | Responsibility |
| --- | --- |
| `frontend/index.html` | Self-contained SPA client for the AURORA API. |
| `app/api/app.py` | `create_app(frontend_dir=...)` serves the UI at `/`. |
| `app/api/__main__.py` | Reads `AURORA_FRONTEND_DIR` to enable the UI. |

## The client

A single, dependency-free, theme-aware page (light/dark) with four tabs, each
mapping to a service endpoint:

- **Chat** — streams tokens over the `/ws/chat` WebSocket.
- **Plan** — `POST /plan`, renders the ordered steps + context files.
- **Review** — `POST /review`, renders findings + summary.
- **Implement** — `POST /implement` with an *approve* checkbox (dry run by
  default), renders the proposed file and write status.

A provider selector (populated from `/providers`) lets the user force a provider
across all tabs; structured API errors are surfaced inline.

## Consistency fix (found by running it)

Running the UI revealed that `/plan`, `/review`, and `/implement` ignored
provider preferences (only `/chat` honored them), so the selector had no effect
and `/review` always auto-routed to the local model. Preferences
(`prefer_provider` / `prefer_model`) are now threaded through the planning,
review, and implementation services, their request schemas, and the endpoints —
consistent with `/chat`.

## Verified live

Served the UI and drove every tab's endpoint against a running server (mock
provider over real HTTP): `GET /` returns the page; Plan, Review, Implement
(approve → file written), and Chat SSE all return 200. WebSocket streaming is
covered by the test suite.

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 3 new (169 total) | ✓ this file | ✓ via API | ✓ inline error display | ✓ strict | ✓ Ruff + Black | ✓ UI ↔ API only |

## Project status

The full AEGIS structure is now implemented, tested, and verified live:

```
core · config · providers · tools · filesystem · terminal · git ·
database · memory · context · router · agents · services · api · frontend
```
