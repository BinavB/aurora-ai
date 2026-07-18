// Thin client for the AURORA backend HTTP API.
//
// The heavy lifting (routing, agents, tools) lives in the Python backend; this
// extension is a client. The base URL is resolved at call time: the configured
// primary (a local `aurora-api`) is preferred, falling back to the hosted URL
// when the primary is unreachable. Uses the global `fetch` shipped with the
// extension host's Node runtime.

import * as vscode from "vscode";

export interface ChatReply {
  provider: string;
  model: string;
  content: string;
}

export interface Capabilities {
  vision: boolean;
  audio: boolean;
  agent: boolean;
}

export class AuroraClient {
  private cachedBase: string | undefined;

  /** Resolve a reachable base URL, preferring the configured primary. */
  async resolveBase(force = false): Promise<string> {
    if (this.cachedBase && !force) {
      return this.cachedBase;
    }
    const cfg = vscode.workspace.getConfiguration("aurora");
    const primary = (cfg.get<string>("apiUrl") || "").replace(/\/+$/, "");
    const fallback = (cfg.get<string>("fallbackUrl") || "").replace(/\/+$/, "");
    for (const base of [primary, fallback].filter(Boolean)) {
      if (await this.isHealthy(base)) {
        this.cachedBase = base;
        return base;
      }
    }
    throw new Error(
      "No AURORA backend reachable. Start a local `aurora-api` server or set " +
        "`aurora.apiUrl` / `aurora.fallbackUrl` in settings."
    );
  }

  private async isHealthy(base: string): Promise<boolean> {
    try {
      const res = await fetch(`${base}/health`, {
        signal: AbortSignal.timeout(2500),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  async get<T>(path: string): Promise<T> {
    const base = await this.resolveBase();
    const res = await fetch(`${base}${path}`);
    return this.parse<T>(res);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    const base = await this.resolveBase();
    const res = await fetch(`${base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return this.parse<T>(res);
  }

  private async parse<T>(res: Response): Promise<T> {
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (!res.ok) {
      const msg =
        (data.message as string) ||
        (data.detail as string) ||
        `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return data as T;
  }

  capabilities(): Promise<Capabilities> {
    return this.get<Capabilities>("/capabilities");
  }
}

/** Prefix a prompt with the configured persona's style hint (mirrors the web UI). */
export function withPersona(text: string): string {
  const persona = vscode.workspace
    .getConfiguration("aurora")
    .get<string>("persona", "neutral");
  const styles: Record<string, string> = {
    friendly: "Respond in a warm, friendly, encouraging tone.",
    witty: "Respond with a witty, playful, slightly cheeky sense of humor.",
    empathetic: "Respond with warmth and empathy.",
    professional: "Respond in a concise, professional, businesslike tone.",
    hype: "Respond with high energy and enthusiasm.",
    socratic: "Respond by guiding with thoughtful questions and reasoning.",
  };
  const style = styles[persona];
  return style ? `[Style: ${style}]\n\n${text}` : text;
}
