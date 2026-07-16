# Milestone 8 — Agents

Status: **complete**, awaiting acceptance.

Implements the architecture's **Agents** layer: single-task orchestrators that
communicate only through injected interfaces.

## Delivered

| Agent | Module | Task | Depends on (interfaces) |
| --- | --- | --- | --- |
| Planner | `planner.py` | Task → ordered plan | `LLMProvider` |
| Coder | `coder.py` | Instruction → full file contents | `LLMProvider` |
| Reviewer | `reviewer.py` | Code → findings + summary | `LLMProvider` |
| Conversation | `conversation.py` | Stateful chat turn | `LLMProvider`, `MemoryStore` |
| Context Builder | `context_builder.py` | Query → built context | `ContextEngine` |
| Executor | `executor.py` | Apply actions | `ToolRegistry` (fs + terminal) |

Supporting modules: `base.py` (`BaseAgent[RequestT, ResultT]`), `llm.py`
(provider-interface completion + text parsing), `models.py` (typed I/O).

## Architecture compliance

- **One task per agent** — each agent has a single `run`.
- **No direct external calls** — LLM agents build provider-agnostic messages and
  call the `LLMProvider` interface; the executor performs no filesystem/terminal
  I/O itself, dispatching every action to the tool registries.
- **Interfaces only** — agents depend on `LLMProvider`, `ToolRegistry`,
  `MemoryStore`, `ContextEngine` — never on provider or tool internals.
- **Separation of generation and side effects** — the coder proposes content;
  the executor writes it via tools.
- **Router / Memory** are their own layers (Milestones 7 / 5) and are consumed
  as interfaces here, not re-wrapped (no duplicated logic).

## Verified behaviour

Planner parses numbered steps; coder strips code fences; reviewer extracts
bullet findings and a `Summary:` line; conversation persists turns and grows
context across turns; context builder surfaces the right file; executor applies
a write + command through tools and reports a dangerous-command refusal as a
structured failure (never raising).

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 7 new (150 total) | ✓ this file | ✓ via lower layers | ✓ structured, non-raising executor | ✓ strict | ✓ Ruff + Black | ✓ interfaces only, one task each |

## Next milestone (not started)

**Services** (`app/services`) — coordinate business logic: API → Services →
Agents → Tools → Providers. Wire the router, context engine, providers, memory,
and agents into cohesive use cases (chat, plan, implement, review).
