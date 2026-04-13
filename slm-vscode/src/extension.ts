import * as vscode from "vscode"
import { registerChatParticipant } from "./chat-participant"

/**
 * Activate the SLM VS Code extension.
 * Registers the @slm chat participant and commands.
 */
export function activate(context: vscode.ExtensionContext): void {
  // Register the chat participant
  registerChatParticipant(context)

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
