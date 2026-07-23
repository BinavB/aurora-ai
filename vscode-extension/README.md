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

## Release process

Bump `version` in `package.json`, then build, package, and install:

```bash
cd vscode-extension
npm install
npm run compile                          # tsc -> dist/
npx vsce package                         # -> aurora-ai-<version>.vsix
code --install-extension aurora-ai-<version>.vsix --force
```

Then reload VS Code (**Developer: Reload Window**). To publish to the Marketplace:

```bash
npx vsce login <publisher>   # create one at https://marketplace.visualstudio.com/manage
npx vsce publish
```

## Version notes

- **0.3.0** — Adds the **engineer** persona (`aurora.persona: "engineer"`):
  verify-before-answer, state assumptions/risks, explain decisions. Backed by the
  backend's enforced engineering behavior (anti-hallucination guard, evidence
  tracking, completion gate). Requires re-running the release steps above.
- **0.2.0** — IDE-native agent: diff/apply for Implement, agent runs against the
  open workspace, integrated terminal transcript, opens changed files.

MIT licensed.
