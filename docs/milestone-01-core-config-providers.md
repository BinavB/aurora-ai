# Milestone 1 — Core, Config, Providers

Status: **complete**, awaiting acceptance.

Implements the three foundational layers of the AEGIS architecture (package
name kept as `aurora` per project decision). Structure lives under
`src/aurora/app/` to match the spec's `app/` layout without breaking the
pre-existing modules.

## Delivered layers

### `app/core`
Shared foundation with no business logic and no dependency on other layers.

| Module | Responsibility |
| --- | --- |
| `constants.py` | App-wide constants (name, version, defaults, secret-key hints). |
| `exceptions.py` | `AuroraError` hierarchy with machine-readable `code` + `to_dict()`. |
| `logging.py` | Centralized JSON logging with recursive secret **redaction**. |
| `events.py` | Async `EventBus` (publish/subscribe) with failure isolation. |
| `container.py` | Dependency-injection `Container` (singletons + lazy factories). |
| `types.py` | Provider-agnostic domain types (`Message`, `Role`, `ChatRequest`, ...). |

### `app/config`
Typed settings (`AppSettings`, `ProviderSettings`) and an environment loader.
Depends only on `core`. API keys are read but never logged.

### `app/providers`
LLM communication behind one interface.

- `interface.py` — `LLMProvider` Protocol (higher layers depend on this).
- `base.py` — `BaseProvider`: HTTP lifecycle, uniform error wrapping,
  structured logging, event emission (`provider.request` / `provider.response`).
- `registry.py` — decorator-based `register_provider`, `build_provider`.
- Concrete: `ollama`, `openai`, `anthropic`, `xai` (OpenAI-compatible),
  `gemini`. No provider references another.

## Definition of Done

| Criterion | Status |
| --- | --- |
| Code compiles | ✓ `compileall` clean |
| Tests pass | ✓ 29 new tests (75 total) |
| Documentation updated | ✓ this file |
| Logging added | ✓ structured, redacting logger |
| Error handling included | ✓ structured `AuroraError` subclasses |
| Type hints complete | ✓ strict typing throughout |
| Lint passes | ✓ Ruff + Black clean |
| Architecture preserved | ✓ downward-only dependencies |

## Configuration

| Env var | Purpose |
| --- | --- |
| `AURORA_LOG_LEVEL` | Log level (default `INFO`). |
| `AURORA_<PROVIDER>_BASE_URL` | Override a provider endpoint. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `XAI_API_KEY` / `GEMINI_API_KEY` | Provider credentials. |

## Next milestone (not started)

Per the Milestone Policy, work stops here pending acceptance. The natural next
layer is **Tools** (`app/tools`) with its input/output schemas, validation, and
permission metadata — followed by Filesystem/Terminal/Git tools.
