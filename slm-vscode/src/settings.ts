import * as vscode from "vscode"

export interface SLMSettings {
  apiKey: string
  apiUrl: string
  mode: "quality" | "fast"
}

/**
 * Read SLM extension settings from VS Code configuration.
 */
export function getSettings(): SLMSettings {
  const config = vscode.workspace.getConfiguration("slm")
  return {
    apiKey: config.get<string>("apiKey", ""),
    apiUrl: config.get<string>("apiUrl", "https://slm.dev/api"),
    mode: config.get<"quality" | "fast">("mode", "quality"),
  }
}

/**
 * Build HTTP headers for API requests.
 */
export function buildHeaders(apiKey: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  }
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`
  }
  return headers
}
