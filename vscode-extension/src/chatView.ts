// The AURORA sidebar chat: a WebviewView backed by the backend chat API.

import * as vscode from "vscode";
import { AuroraClient, ChatReply, withPersona } from "./api";

interface CollaborateReply {
  content: string;
}

export class AuroraChatViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "aurora.chat";
  private view?: vscode.WebviewView;
  private readonly sessionId = "vscode-" + Math.random().toString(36).slice(2);

  constructor(private readonly client: AuroraClient) {}

  resolveWebviewView(view: vscode.WebviewView): void {
    this.view = view;
    view.webview.options = { enableScripts: true };
    view.webview.html = this.html(view.webview);
    view.webview.onDidReceiveMessage((msg) => {
      if (msg?.type === "send") {
        void this.handleSend(String(msg.text ?? ""));
      }
    });
  }

  private async handleSend(text: string): Promise<void> {
    const webview = this.view?.webview;
    if (!webview || !text.trim()) {
      return;
    }
    const effort = vscode.workspace
      .getConfiguration("aurora")
      .get<string>("effort", "fast");
    try {
      let reply: string;
      let meta: string;
      if (effort !== "fast") {
        const data = await this.client.post<CollaborateReply>("/collaborate", {
          task: withPersona(text),
          mode: "chat",
          effort,
        });
        reply = data.content;
        meta = `${effort} · team`;
      } else {
        const data = await this.client.post<ChatReply>("/chat", {
          session_id: this.sessionId,
          message: withPersona(text),
        });
        reply = data.content;
        meta = `${data.provider} · ${data.model}`;
      }
      webview.postMessage({ type: "reply", text: reply, meta });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      webview.postMessage({ type: "error", text: message });
    }
  }

  private html(webview: vscode.Webview): string {
    const nonce = Math.random().toString(36).slice(2);
    const csp =
      `default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; ` +
      `script-src 'nonce-${nonce}';`;
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="${csp}" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    body { margin: 0; font-family: var(--vscode-font-family); color: var(--vscode-foreground);
      font-size: var(--vscode-font-size); display: flex; flex-direction: column; height: 100vh; }
    #log { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 10px; }
    .msg { padding: 8px 10px; border-radius: 8px; white-space: pre-wrap; word-break: break-word; line-height: 1.45; }
    .user { align-self: flex-end; background: var(--vscode-input-background); border: 1px solid var(--vscode-input-border, transparent); max-width: 90%; }
    .bot { background: var(--vscode-editorWidget-background); border: 1px solid var(--vscode-widget-border, transparent); max-width: 95%; }
    .err { color: var(--vscode-errorForeground); }
    .meta { font-size: 0.8em; opacity: 0.6; margin-top: 4px; }
    .hint { opacity: 0.6; text-align: center; margin-top: 20%; padding: 0 12px; }
    form { display: flex; gap: 6px; padding: 8px; border-top: 1px solid var(--vscode-widget-border, rgba(128,128,128,0.2)); }
    textarea { flex: 1; resize: none; background: var(--vscode-input-background); color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, transparent); border-radius: 6px; padding: 6px 8px; font-family: inherit; font-size: inherit; }
    button { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 6px; padding: 0 12px; cursor: pointer; }
    button:hover { background: var(--vscode-button-hoverBackground); }
  </style>
</head>
<body>
  <div id="log"><div class="hint">Ask AURORA anything about your code.</div></div>
  <form id="f">
    <textarea id="i" rows="2" placeholder="Ask AURORA… (Enter to send)"></textarea>
    <button type="submit">Send</button>
  </form>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const log = document.getElementById("log");
    const input = document.getElementById("i");
    const form = document.getElementById("f");
    let pending = null;
    function add(cls, text, meta) {
      const hint = log.querySelector(".hint"); if (hint) hint.remove();
      const d = document.createElement("div");
      d.className = "msg " + cls; d.textContent = text;
      if (meta) { const m = document.createElement("div"); m.className = "meta"; m.textContent = meta; d.appendChild(m); }
      log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
    }
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = input.value.trim(); if (!text) return;
      add("user", text); input.value = "";
      pending = add("bot", "…");
      vscode.postMessage({ type: "send", text });
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
    });
    window.addEventListener("message", (ev) => {
      const m = ev.data;
      if (!pending) return;
      if (m.type === "reply") { pending.textContent = m.text; if (m.meta) { const mt = document.createElement("div"); mt.className = "meta"; mt.textContent = m.meta; pending.appendChild(mt); } }
      else if (m.type === "error") { pending.textContent = m.text; pending.classList.add("err"); }
      pending = null; log.scrollTop = log.scrollHeight;
    });
  </script>
</body>
</html>`;
  }
}
