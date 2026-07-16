# Milestone 2 — Tool System + Filesystem Tools

Status: **complete**, awaiting acceptance.

Implements the architecture's **Tool System** and **Filesystem Rules**. Later
milestones add Terminal and Git tools on the same framework.

## Delivered

### `app/tools` — the tool framework
| Module | Responsibility |
| --- | --- |
| `models.py` | `Permission` enum, `ToolMetadata`, structured `ToolResult`. |
| `base.py` | `BaseTool[InputT, OutputT]`: typed schemas, validation, permission checks, structured results. |
| `registry.py` | `ToolRegistry` — register/discover/invoke by name. |

Every tool exposes, per the spec: **input schema, output schema, metadata,
validation, and permission requirements** (`BaseTool.spec()`), and returns
**structured data only** — `ToolResult` with `data` or `error`, never raw text,
never an uncaught exception.

### `app/tools/filesystem` — the only path to the filesystem
| Module | Responsibility |
| --- | --- |
| `paths.py` | `PathSandbox`: normalize paths, reject absolute paths and `..` traversal. |
| `io.py` | Atomic writes (temp file + `os.replace` + `fsync`); `.bak` backup before overwrite. |
| `models.py` | Typed input/output models per tool. |
| `tools.py` | `ReadFile`, `WriteFile`, `DeleteFile`, `RenameFile`, `SearchProject`. |

Filesystem rules honored: atomic writes ✓, backups before overwrite ✓, path
normalization ✓, traversal prevention ✓, cross-platform (`pathlib`) ✓.

## Permissions

Tools declare required `Permission`s (`read`, `write`, `delete`, ...). The
registry's `invoke(..., granted=...)` enforces them: a caller lacking a
permission gets a structured `permission_denied` result. `granted=None` means a
trusted caller (all permissions).

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 16 new (91 total) | ✓ this file | ✓ per-tool logger | ✓ structured `ToolError` | ✓ strict | ✓ Ruff + Black | ✓ tools own all file access |

## Next milestone (not started)

**Terminal tools** (`app/terminal`) — capture stdout/stderr/exit code/duration,
support streaming, and require confirmation for dangerous commands. Then **Git
tools** (`app/git`) — status/diff/commit with no auto-commit or auto-push.
