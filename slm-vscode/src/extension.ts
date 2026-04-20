import * as vscode from "vscode"
import { registerChatParticipant } from "./chat-participant"
import { registerAutocomplete } from "./autocomplete"
import { registerDiagnostics } from "./diagnostics"
import { registerStatusBar } from "./status-bar"

/**
 * Activate the Sealevel VS Code extension.
 * Registers the @slm chat participant, commands, inline completions,
 * deprecated-pattern diagnostics, status bar, and output channel.
 */
export function activate(context: vscode.ExtensionContext): void {
  // Output channel for debug logs
  const output = vscode.window.createOutputChannel("Sealevel")
  context.subscriptions.push(output)
  output.appendLine(`[${new Date().toISOString()}] Sealevel extension activated`)

  // Register the chat participant
  registerChatParticipant(context)

  // Status bar indicator + health polling
  registerStatusBar(context, output)

  // Deprecated-pattern diagnostics + quick-fix code actions
  registerDiagnostics(context)

  // Register inline autocomplete
  const config = vscode.workspace.getConfiguration("slm")
  if (config.get<boolean>("autocomplete.enabled", true)) {
    registerAutocomplete(context)
  }

  // Register explain error command
  const explainError = vscode.commands.registerCommand(
    "slm.explainError",
    async () => {
      const errorCode = await vscode.window.showInputBox({
        prompt: "Enter a Solana error code (decimal or hex)",
        placeHolder: "e.g., 0x1771 or 6001",
      })

      if (errorCode) {
        // Open the chat with the error explanation prompt
        await vscode.commands.executeCommand(
          "workbench.action.chat.open",
          `@slm Explain Solana error code ${errorCode}`,
        )
      }
    },
  )

  // Register explain tx command
  const explainTx = vscode.commands.registerCommand(
    "slm.explainTx",
    async () => {
      const signature = await vscode.window.showInputBox({
        prompt: "Enter a Solana transaction signature",
        placeHolder: "e.g., 5U3...",
      })

      if (signature) {
        await vscode.commands.executeCommand(
          "workbench.action.chat.open",
          `@slm Explain this Solana transaction: ${signature}`,
        )
      }
    },
  )

  context.subscriptions.push(explainError, explainTx)
}

export function deactivate(): void {
  // Cleanup if needed
}
