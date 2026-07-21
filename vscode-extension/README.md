# AURORA AI — VS Code extension

A provider-agnostic AI engineering assistant in your editor, powered by an
[AURORA](https://github.com/BinavB/aurora-ai) backend. Chat, explain, review,
implement, and run an autonomous agent — across 9 model providers with
automatic failover.

## Features

- **Sidebar chat** (AURORA icon in the activity bar) — persona- and effort-aware.
- **AURORA: Explain Selection** — explain the selected code (or whole file).
- **AURORA: Review File / Selection** — structured findings + summary.
- **AURORA: Implement…** — generate a file from an instruction, preview it as a **diff against the current file**, and **write it to disk** on approval.
- **AURORA: Run Autonomous Agent…** — a ReAct loop that reads/writes files and runs commands in **your open workspace folder**. It mirrors the commands it runs into an integrated **AURORA Agent** terminal and opens the files it changed. (Requires a local backend with the agent enabled.)

The extension sends the open workspace folder to the backend, so `implement` and
the agent act on **your project** rather than the server's launch directory. A
client-supplied workspace is honored only by a trusted local backend (one with
`AURORA_ENABLE_AGENT=1`); a hosted backend always ignores it.

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
