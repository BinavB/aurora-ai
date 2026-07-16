# Milestone 6 — Context Engine

Status: **complete**, awaiting acceptance.

Implements the architecture's **Context Engine**: a token-efficient pipeline
that never loads entire repositories.

## Pipeline (understand → locate → extract → compress → build)

| Stage | Module | Interface | Default |
| --- | --- | --- | --- |
| 1. Understand | `analyzer.py` | `QueryAnalyzer` | `KeywordQueryAnalyzer` |
| 2. Locate | `locator.py` | `FileLocator` | `SearchFileLocator` |
| 3. Extract symbols | `extractor.py` | `SymbolExtractor` | `PythonSymbolExtractor` |
| 4. Compress | `compressor.py` | `ContextCompressor` | `SymbolAwareCompressor` |
| 5. Build prompt | `builder.py` | `PromptBuilder` | `MessagePromptBuilder` |

`engine.py` (`ContextEngine`) composes the stages; each is injectable, so any
stage can be replaced without touching the others.

## Token efficiency (mandatory, per spec)

- **Never loads whole repos** — the locator scores files via the
  `search_project` filesystem tool (hit counts per term), then only the
  top-`max_files` candidates are read.
- **Compression** — a chunk is the file's symbol signatures plus the lines that
  mention query terms, trimmed to the remaining token budget; whole files are
  not embedded.
- **Hard budget** — `ContextRequest.max_tokens` bounds the assembled context;
  when it is exhausted the result is flagged `truncated`.

## Architecture compliance

- **No direct filesystem access** — the engine reads and searches solely through
  the filesystem tools (Milestone 2), never `open()`.
- Symbol extraction runs `ast.parse` on file *content* (a string), not on files.

## Verified behaviour

Against a small temp project: the query "issue a token for the manager" ranks
`auth.py` first and surfaces `TokenManager` in the context block; a tight
5-token budget truncates; an unmatched query yields a valid system+user prompt
with no context block.

## Definition of Done

| Compiles | Tests | Docs | Logging | Errors | Types | Lint | Architecture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ✓ | ✓ 7 new (132 total) | ✓ this file | ✓ engine logs build | ✓ tool errors handled | ✓ strict | ✓ Ruff + Black | ✓ file access via tools only |

## Next milestone (not started)

**Router** (`app/router`) — decide provider/model/tools/context from model
capability, availability, offline mode, cost, and user preference.
