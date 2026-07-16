# Milestone 3 — Terminal Tools

Status: **complete**, awaiting acceptance.

Implements the architecture's **Terminal Rules** on the Milestone 2 tool
framework. Located at `app/tools/terminal` (same nesting as `filesystem`).

## Delivered

| Module | Responsibility |
| --- | --- |
| `safety.py` | `dangerous_reason()` — flags destructive commands and patterns. |
| `models.py` | `CommandResult`, `StreamLine`, `RunTerminalInput`, `RunTestsInput`. |
| `runner.py` | `TerminalRunner` — async exec with capture + line streaming. |
| `tools.py` | `RunTerminalTool`, `RunTestsTool`. |

## Terminal rules honored

- **Only terminal tools execute commands** — execution lives solely here.
- **No shell injection** — commands run via `create_subprocess_exec` as an
  argument vector; there is no shell, so `;`, `|`, `&&` are inert literals.
- **Full capture** — stdout, stderr, exit code, and wall-clock
  `duration_seconds` (via `time.perf_counter`).
- **Streaming** — `TerminalRunner.stream()` yields `StreamLine`s as output
  arrives (cross-platform line endings normalized).
- **Timeouts** — commands exceeding their timeout are killed and reported with
  `timed_out=True`, `exit_code=-1`.
- **Confirmation for dangerous commands** — `RunTerminalTool` refuses a
  destructive command unless `confirm=true`, returning a structured
  `confirmation_required` error.
- **Permissions** — both tools require `Permission.EXECUTE`.

The working directory is sandboxed (reusing `PathSandbox`); an out-of-sandbox or
non-existent `cwd` is rejected.

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 18 new (109 total) | ✓ this file | ✓ runner logs | ✓ structured `ToolError` | ✓ strict | ✓ Ruff + Black | ✓ terminal tools own all execution |

## Next milestone (not started)

**Git tools** (`app/tools/git`) — `GitStatus`, `GitDiff`, `GitCommit`, built on
`TerminalRunner`, with **no auto-commit and no auto-push** (commit/push require
explicit approval).
