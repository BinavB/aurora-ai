// AURORA VS Code extension entry point.
//
// Native sidebar chat plus editor-context commands (explain, review, implement,
// autonomous agent). All model work happens in the AURORA backend; this layer
// gathers editor context, calls the API, and surfaces results in the IDE.

import * as vscode from "vscode";
import { AuroraClient, withPersona } from "./api";
import { AuroraChatViewProvider } from "./chatView";

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

interface AgentResult {
  report: {
    completed: boolean;
    answer: string;
    steps: {
      index: number;
      tool: string | null;
      ok: boolean | null;
      observation: string;
    }[];
  };
}

export function activate(context: vscode.ExtensionContext): void {
  const client = new AuroraClient();
  const chat = new AuroraChatViewProvider(client);
  const output = vscode.window.createOutputChannel("AURORA");

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
    prompt: "Target file name",
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
        approve: false,
      })
  );
  const doc = await vscode.workspace.openTextDocument({
    content: result.proposed.content,
  });
  await vscode.window.showTextDocument(doc);
  void vscode.window.showInformationMessage(
    `AURORA generated ${result.proposed.path} (${result.provider}/${result.model}). Review, then save where you want.`
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
    () => client.post<AgentResult>("/agent", { task: withPersona(task) })
  );
  for (const step of result.report.steps) {
    const flag = step.ok === false ? " ✗" : "";
    const obs = (step.observation || "").slice(0, 140);
    output.appendLine(`  ${step.index}. ${step.tool ?? "done"}${flag}  ${obs}`);
  }
  output.appendLine(
    `\n${result.report.completed ? "✔ completed" : "■ stopped"}: ${result.report.answer}`
  );
  void vscode.window.showInformationMessage(
    `AURORA agent ${result.report.completed ? "completed" : "stopped"} — see the AURORA output channel.`
  );
}
