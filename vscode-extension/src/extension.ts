// AURORA VS Code extension entry point.
//
// Native sidebar chat plus editor-context commands (explain, review, implement,
// autonomous agent). The model work happens in the AURORA backend; this layer
// gathers editor context, calls the API, and applies results *in the IDE*:
// implement writes files after a diff review, and the agent operates on the open
// workspace folder, mirroring its terminal commands and opening changed files.

import * as vscode from "vscode";
import { AuroraClient, withPersona } from "./api";
import { AuroraChatViewProvider } from "./chatView";
import {
  openPaths,
  registerIde,
  reviewAndApply,
  TranscriptTerminal,
  workspaceFolderPath,
} from "./ide";

interface ReviewOutcome {
  provider: string;
  model: string;
  result: { summary: string; findings: string[] };
}

interface ImplementResult {
  provider: string;
  model: string;
  proposed: { path: string; content: string };
}

interface ToolCallInfo {
  tool: string | null;
  ok: boolean | null;
  observation: string;
  args?: Record<string, unknown>;
}

interface AgentStepInfo extends ToolCallInfo {
  index: number;
  calls?: ToolCallInfo[];
}

interface AgentResult {
  report: { completed: boolean; answer: string; steps: AgentStepInfo[] };
}

export function activate(context: vscode.ExtensionContext): void {
  const client = new AuroraClient();
  const chat = new AuroraChatViewProvider(client);
  const output = vscode.window.createOutputChannel("AURORA");
  registerIde(context);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      AuroraChatViewProvider.viewType,
      chat
    ),
    output,
    vscode.commands.registerCommand("aurora.focusChat", () =>
      vscode.commands.executeCommand("aurora.chat.focus")
    ),
    vscode.commands.registerCommand("aurora.explain", () =>
      guard(() => explain(client))
    ),
    vscode.commands.registerCommand("aurora.review", () =>
      guard(() => review(client))
    ),
    vscode.commands.registerCommand("aurora.implement", () =>
      guard(() => implement(client))
    ),
    vscode.commands.registerCommand("aurora.agent", () =>
      guard(() => runAgent(client, output))
    )
  );
}

export function deactivate(): void {
  // nothing to clean up
}

function guard(fn: () => Promise<void>): void {
  fn().catch((err) => {
    const message = err instanceof Error ? err.message : String(err);
    void vscode.window.showErrorMessage(`AURORA: ${message}`);
  });
}

/** The active editor's code (selection if any) and workspace-relative path. */
function activeCode(): { code: string; path: string } | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    void vscode.window.showWarningMessage("AURORA: open a file first.");
    return undefined;
  }
  const selection = editor.selection;
  const code = selection.isEmpty
    ? editor.document.getText()
    : editor.document.getText(selection);
  return { code, path: vscode.workspace.asRelativePath(editor.document.uri) };
}

async function showMarkdown(title: string, body: string): Promise<void> {
  const doc = await vscode.workspace.openTextDocument({
    language: "markdown",
    content: `# ${title}\n\n${body}\n`,
  });
  await vscode.window.showTextDocument(doc, { preview: true });
}

async function explain(client: AuroraClient): Promise<void> {
  const target = activeCode();
  if (!target) {
    return;
  }
  const reply = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "AURORA explaining…" },
    () =>
      client.post<{ content: string }>("/chat", {
        session_id: "vscode-explain",
        message: withPersona(
          `Explain this code clearly and concisely:\n\n\`\`\`\n${target.code}\n\`\`\``
        ),
      })
  );
  await showMarkdown(`Explain — ${target.path}`, reply.content);
}

async function review(client: AuroraClient): Promise<void> {
  const target = activeCode();
  if (!target) {
    return;
  }
  const outcome = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "AURORA reviewing…" },
    () => client.post<ReviewOutcome>("/review", { code: target.code })
  );
  const findings =
    outcome.result.findings.map((f) => `- ${f}`).join("\n") || "_No findings._";
  await showMarkdown(
    `Review — ${target.path}`,
    `**Summary:** ${outcome.result.summary}\n\n${findings}\n\n_${outcome.provider} / ${outcome.model}_`
  );
}

async function implement(client: AuroraClient): Promise<void> {
  const instruction = await vscode.window.showInputBox({
    prompt: "What should AURORA build?",
    placeHolder: "e.g. a FastAPI health-check endpoint",
  });
  if (!instruction) {
    return;
  }
  const active = vscode.window.activeTextEditor;
  const target = await vscode.window.showInputBox({
    prompt: "Target file (relative to the workspace)",
    value: active ? vscode.workspace.asRelativePath(active.document.uri) : "index.html",
  });
  if (!target) {
    return;
  }
  const result = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "AURORA implementing…" },
    () =>
      client.post<ImplementResult>("/implement", {
        instruction: withPersona(instruction),
        target_path: target,
        approve: false, // generate only; the IDE applies after review
        workspace: workspaceFolderPath(),
      })
  );
  const path = result.proposed.path || target;
  const applied = await reviewAndApply(path, result.proposed.content);
  void vscode.window.showInformationMessage(
    applied
      ? `AURORA applied ${path} (${result.provider}/${result.model}).`
      : `AURORA left ${path} unchanged.`
  );
}

async function runAgent(
  client: AuroraClient,
  output: vscode.OutputChannel
): Promise<void> {
  const caps = await client.capabilities();
  if (!caps.agent) {
    void vscode.window.showErrorMessage(
      "AURORA: the autonomous agent is disabled on this backend. Run a local " +
        "`aurora-api` with AURORA_ENABLE_AGENT=1 and point `aurora.apiUrl` at it."
    );
    return;
  }
  const task = await vscode.window.showInputBox({
    prompt: "Task for the autonomous agent — it will read, write, and run in your workspace.",
    placeHolder: "e.g. add type hints to utils.py and run the tests",
  });
  if (!task) {
    return;
  }
  output.show(true);
  output.appendLine(`\n▶ ${task}`);
  const result = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "AURORA agent running…" },
    () =>
      client.post<AgentResult>("/agent", {
        task: withPersona(task),
        workspace: workspaceFolderPath(),
      })
  );

  const terminal = new TranscriptTerminal();
  const changed: string[] = [];
  for (const step of result.report.steps) {
    const flag = step.ok === false ? " ✗" : "";
    const obs = (step.observation || "").slice(0, 140);
    output.appendLine(`  ${step.index}. ${step.tool ?? "done"}${flag}  ${obs}`);
    for (const call of effectiveCalls(step)) {
      routeCall(call, terminal, changed);
    }
  }
  output.appendLine(
    `\n${result.report.completed ? "✔ completed" : "■ stopped"}: ${result.report.answer}`
  );
  if (changed.length) {
    await openPaths(changed);
  }
  void vscode.window.showInformationMessage(
    `AURORA agent ${result.report.completed ? "completed" : "stopped"} — ` +
      `${changed.length} file(s) changed. See the AURORA output channel.`
  );
}

/** Flatten a step into its tool calls (a step may batch several). */
function effectiveCalls(step: AgentStepInfo): ToolCallInfo[] {
  if (step.calls && step.calls.length) {
    return step.calls;
  }
  return step.tool ? [step] : [];
}

/** Route a tool call to the terminal transcript or the changed-files list. */
function routeCall(
  call: ToolCallInfo,
  terminal: TranscriptTerminal,
  changed: string[]
): void {
  const args = call.args ?? {};
  switch (call.tool) {
    case "run_terminal": {
      const cmd = Array.isArray(args.command)
        ? (args.command as unknown[]).join(" ")
        : String(args.command ?? "");
      terminal.command(cmd, commandOutput(call.observation));
      break;
    }
    case "run_tests": {
      const path = typeof args.path === "string" ? args.path : "";
      const extra = Array.isArray(args.extra_args)
        ? (args.extra_args as unknown[]).join(" ")
        : "";
      terminal.command(`pytest ${path} ${extra}`.trim(), commandOutput(call.observation));
      break;
    }
    case "write_file":
      if (typeof args.path === "string") {
        changed.push(args.path);
      }
      break;
    case "rename_file":
      if (typeof args.dst === "string") {
        changed.push(args.dst);
      }
      break;
    default:
      break;
  }
}

/** Extract readable stdout/stderr from a captured-command observation. */
function commandOutput(observation: string): string {
  try {
    const data = JSON.parse(observation) as { stdout?: string; stderr?: string };
    return [data.stdout, data.stderr].filter(Boolean).join("\n") || observation;
  } catch {
    return observation;
  }
}
