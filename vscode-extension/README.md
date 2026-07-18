# AURORA AI — VS Code extension

A provider-agnostic AI engineering assistant in your editor, powered by an
[AURORA](https://github.com/BinavB/aurora-ai) backend. Chat, explain, review,
implement, and run an autonomous agent — across 9 model providers with
automatic failover.

## Features

- **Sidebar chat** (AURORA icon in the activity bar) — persona- and effort-aware.
- **AURORA: Explain Selection** — explain the selected code (or whole file).
- **AURORA: Review File / Selection** — structured findings + summary.
- **AURORA: Implement…** — generate a file from an instruction; opens in the editor for you to save.
- **AURORA: Run Autonomous Agent…** — a ReAct loop that reads/writes files and runs commands in your workspace (requires a local backend with the agent enabled).

## Requirements

The extension is a client for an AURORA backend. Point it at one via settings:

- `aurora.apiUrl` — primary backend (default `http://127.0.0.1:8000`, a local `aurora-api`).
- `aurora.fallbackUrl` — used when the primary is unreachable (e.g. your hosted deploy).
- `aurora.effort` — `fast` (one model) / `balanced` / `max` (a team).
- `aurora.persona` — response tone.

**Run a local backend** (for full features incl. the agent):

```bash
pip install -e ".[serve]"
# enable the autonomous agent (writes files / runs commands locally):
AURORA_ENABLE_AGENT=1 uvicorn aurora.app.api.__main__:app --port 8000
```

The autonomous agent stays **disabled** on the public/hosted backend for safety;
enable it only on a local, trusted server.

## Build & install locally

```bash
cd vscode-extension
npm install
npm run compile
npx vsce package        # produces aurora-ai-0.1.0.vsix
```

Then in VS Code: **Extensions → ⋯ → Install from VSIX…** and pick the `.vsix`.

## Publish to the Marketplace

```bash
npx vsce login <publisher>   # create a publisher at https://marketplace.visualstudio.com/manage
npx vsce publish
```

MIT licensed.
