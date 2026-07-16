# Milestone 5 — Memory (Database + Memory)

Status: **complete**, awaiting acceptance.

Implements the architecture's **Memory** section: SQLite-first,
provider-independent persistence behind repository interfaces.

## Delivered

### `app/database` — persistence engine
| Module | Responsibility |
| --- | --- |
| `schema.py` | Idempotent DDL: `conversations`, `records`, `kv`. |
| `engine.py` | `Database` — async, serialized SQLite (via `asyncio.to_thread` + lock). |

The engine wraps stdlib `sqlite3` (no new dependency); calls run off the event
loop and are serialized behind a lock for safe single-connection access.

### `app/memory` — repositories + facade
| Module | Responsibility |
| --- | --- |
| `models.py` | `StoredMessage`, `Record`, `RecordKind` (decision/fix/issue/note). |
| `interfaces.py` | Abstract `ConversationRepository`, `RecordRepository`, `KeyValueRepository` (**repository pattern**). |
| `repositories.py` | SQLite implementations of each interface. |
| `store.py` | `MemoryStore` — provider-independent facade. |

## What it stores (per spec)

- **Conversation history** — ordered, per-session, clearable.
- **Architecture decisions / previous fixes / known issues** — `records` with a
  `RecordKind`, recallable by kind, newest first.
- **Project metadata / coding style / user preferences / current milestone** —
  namespaced key/value (`NS_PROJECT`, `NS_PREFERENCES`, `NS_STYLE`), with a
  `current_milestone` convenience.

## Key properties

- **Provider-independent** — the memory layer imports nothing from `providers`.
- **Replaceable backend** — callers depend on the interfaces; the SQLite
  implementation can be swapped (e.g. a vector DB) without changes upstream.
- **Persistent** — verified data survives a full close/reopen against a file DB.
- **Deterministic time** — timestamp clock is injectable for testing.

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 9 new (125 total) | ✓ this file | ✓ engine logs connect | ✓ `ConfigurationError` on misuse | ✓ strict | ✓ Ruff + Black | ✓ SQL confined to database/memory |

## Next milestone (not started)

**Context Engine** (`app/context`) — the token-efficient pipeline: understand
request → locate relevant files (via filesystem/search tools) → extract symbols
→ compress → build prompt. Never loads entire repositories.
