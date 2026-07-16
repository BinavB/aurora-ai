# Milestone 4 — Git Tools

Status: **complete**, awaiting acceptance.

Implements the architecture's **Git Rules** on the Milestone 2/3 foundations.
Located at `app/tools/git`, running `git` through the sandboxed
`TerminalRunner`.

## Delivered

| Module | Responsibility |
| --- | --- |
| `models.py` | `StatusEntry`, `GitStatusOutput`, diff/add/commit I/O models. |
| `parser.py` | `parse_status()` — porcelain → structured entries (handles renames). |
| `tools.py` | `GitStatusTool`, `GitDiffTool`, `GitAddTool`, `GitCommitTool`. |

## Git rules honored

- **Git only through git tools** — all git access is confined here, over the
  terminal runner.
- **Never auto-commit** — `GitCommitTool` refuses unless `approve=true`,
  returning a structured `confirmation_required` error (verified: nothing is
  committed on refusal).
- **Never auto-push** — there is **no push tool at all**; nothing can be pushed
  by the platform (verified by test).
- **Structured output** — status is parsed into typed entries; diffs report
  `has_changes`; failures (e.g. not a repo) become a structured `tool_error`,
  never a crash.
- **Permissions** — every git tool requires `Permission.GIT`.

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 7 new (116 total) | ✓ this file | ✓ via runner | ✓ structured | ✓ strict | ✓ Ruff + Black | ✓ git tools own all git access |

## Next milestone (not started)

**Memory** (`app/database` + `app/memory`) — SQLite-first, provider-independent
persistence for conversation history, project metadata, decisions, and the
current milestone, behind a repository-pattern interface.
