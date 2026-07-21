// IDE integration: the pieces that make AURORA act inside the editor rather
// than just talk to it — resolving the open workspace, applying file changes
// with a diff preview, mirroring the agent's terminal commands into a real
// integrated terminal, and opening the files the agent touched.

import * as vscode from "vscode";

/** Absolute path of the first open workspace folder, if any. */
export function workspaceFolderPath(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

/** URI of a workspace-relative path (undefined when no folder is open). */
function targetUri(relPath: string): vscode.Uri | undefined {
  const folder = workspaceFolderPath();
  return folder ? vscode.Uri.joinPath(vscode.Uri.file(folder), relPath) : undefined;
}

// A content provider backing diff previews: it serves AURORA's *proposed* file
// content on a virtual URI so the editor can diff it against the file on disk
// without writing anything until the user approves.
const SCHEME = "aurora-proposed";

class ProposedContentProvider implements vscode.TextDocumentContentProvider {
  private readonly emitter = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange = this.emitter.event;
  private readonly contents = new Map<string, string>();

  set(relPath: string, content: string): vscode.Uri {
    const uri = vscode.Uri.parse(`${SCHEME}:${relPath}`);
    this.contents.set(uri.toString(), content);
    this.emitter.fire(uri);
    return uri;
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    return this.contents.get(uri.toString()) ?? "";
  }
}

const proposed = new ProposedContentProvider();

/** Register the diff-preview content provider (call once, on activation). */
export function registerIde(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(SCHEME, proposed)
  );
}

async function fileExists(uri: vscode.Uri): Promise<boolean> {
  try {
    await vscode.workspace.fs.stat(uri);
    return true;
  } catch {
    return false;
  }
}

/**
 * Show AURORA's proposed content for ``relPath`` (as a diff against the current
 * file, or a preview for a new file), then write it to disk if the user
 * approves. Returns whether the change was applied.
 */
export async function reviewAndApply(
  relPath: string,
  content: string
): Promise<boolean> {
  const target = targetUri(relPath);
  if (!target) {
    void vscode.window.showErrorMessage(
      "AURORA: open a folder in VS Code to apply changes."
    );
    return false;
  }
  const right = proposed.set(relPath, content);
  if (await fileExists(target)) {
    await vscode.commands.executeCommand(
      "vscode.diff",
      target,
      right,
      `AURORA ⟷ ${relPath} (proposed)`
    );
  } else {
    const doc = await vscode.workspace.openTextDocument(right);
    await vscode.window.showTextDocument(doc, { preview: true });
  }

  const choice = await vscode.window.showInformationMessage(
    `Apply AURORA's changes to ${relPath}?`,
    "Apply",
    "Discard"
  );
  if (choice !== "Apply") {
    return false;
  }
  await vscode.workspace.fs.writeFile(target, Buffer.from(content, "utf8"));
  const saved = await vscode.workspace.openTextDocument(target);
  await vscode.window.showTextDocument(saved);
  return true;
}

/** Open the workspace files an agent run created or modified. */
export async function openPaths(paths: string[]): Promise<void> {
  for (const rel of [...new Set(paths)]) {
    const uri = targetUri(rel);
    if (!uri || !(await fileExists(uri))) {
      continue;
    }
    const doc = await vscode.workspace.openTextDocument(uri);
    await vscode.window.showTextDocument(doc, { preview: false });
  }
}

// A read-only integrated terminal that renders a transcript of the commands the
// agent ran (executed on the backend) and their output — so terminal activity
// shows up in the IDE's Terminal panel, like a native agent.
export class TranscriptTerminal {
  private readonly writer = new vscode.EventEmitter<string>();
  private terminal?: vscode.Terminal;

  private ensure(): void {
    if (this.terminal) {
      return;
    }
    const pty: vscode.Pseudoterminal = {
      onDidWrite: this.writer.event,
      open: () => this.writer.fire("AURORA agent — command transcript\r\n\r\n"),
      close: () => undefined,
    };
    this.terminal = vscode.window.createTerminal({ name: "AURORA Agent", pty });
  }

  /** Show a command and its captured output as one transcript entry. */
  command(cmd: string, output: string): void {
    this.ensure();
    this.terminal?.show(true);
    this.writer.fire(`$ ${cmd}\r\n`);
    const body = output.trim();
    if (body) {
      this.writer.fire(body.replace(/\r?\n/g, "\r\n") + "\r\n");
    }
    this.writer.fire("\r\n");
  }
}
