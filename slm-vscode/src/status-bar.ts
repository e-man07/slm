import * as vscode from "vscode"
import { getSettings } from "./settings"

/**
 * Status bar item showing Sealevel connection state.
 * Click → open Sealevel settings.
 */
export function registerStatusBar(context: vscode.ExtensionContext, output: vscode.OutputChannel): vscode.StatusBarItem {
  const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100)
  item.command = "workbench.action.openSettings"
  item.name = "Sealevel"

  async function refresh() {
    const settings = getSettings()
    if (!settings.apiKey) {
      item.text = "$(circle-slash) Sealevel: Not configured"
      item.tooltip = "Click to open settings and set slm.apiKey"
      item.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground")
      return
    }

    // Probe health endpoint
    try {
      const url = settings.apiUrl.replace(/\/api$/, "") + "/health"
      const resp = await fetch(url, { signal: AbortSignal.timeout(3000) })
      if (resp.ok) {
        item.text = "$(check) Sealevel: Ready"
        item.tooltip = `Connected to ${settings.apiUrl}`
        item.backgroundColor = undefined
        output.appendLine(`[${new Date().toISOString()}] health OK (${settings.apiUrl})`)
      } else {
        item.text = "$(warning) Sealevel: Degraded"
        item.tooltip = `Health check returned ${resp.status}`
        item.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground")
      }
    } catch (err) {
      item.text = "$(error) Sealevel: Offline"
      item.tooltip = `Cannot reach ${settings.apiUrl}`
      item.backgroundColor = new vscode.ThemeColor("statusBarItem.errorBackground")
      output.appendLine(
        `[${new Date().toISOString()}] health check failed: ${err instanceof Error ? err.message : String(err)}`,
      )
    }
  }

  item.text = "$(sync~spin) Sealevel"
  item.show()
  void refresh()

  // Refresh every 60 s + on settings change
  const interval = setInterval(refresh, 60_000)
  const disposable = vscode.workspace.onDidChangeConfiguration((e) => {
    if (e.affectsConfiguration("slm")) void refresh()
  })

  context.subscriptions.push(item, disposable, { dispose: () => clearInterval(interval) })
  return item
}
