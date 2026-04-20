import * as vscode from "vscode"
import { getSettings, buildHeaders } from "./settings"

const DEBOUNCE_MS = 1500
const SUPPORTED_LANGUAGES = ["rust", "typescript", "javascript", "toml"]
const MAX_CONTEXT_LINES = 50

let debounceTimer: ReturnType<typeof setTimeout> | undefined

/**
 * Build a completion prompt from the document context around the cursor.
 */
function buildCompletionPrompt(
  document: vscode.TextDocument,
  position: vscode.Position,
): string {
  const startLine = Math.max(0, position.line - MAX_CONTEXT_LINES)
  const prefix = document.getText(
    new vscode.Range(startLine, 0, position.line, position.character),
  )
  const suffix = document.getText(
    new vscode.Range(
      position.line,
      position.character,
      Math.min(document.lineCount - 1, position.line + 10),
      0,
    ),
  )

  return `Continue this Solana/Anchor code. Only output the completion, no explanation, no markdown fences.\n\n${prefix}<CURSOR>${suffix}`
}

/**
 * Request a completion from the Sealevel API.
 */
async function fetchCompletion(
  prompt: string,
  signal: AbortSignal,
): Promise<string | null> {
  const settings = getSettings()
  const headers = buildHeaders(settings.apiKey)

  const url = settings.apiUrl.replace(/\/api$/, "")
  const endpoint = `${url}/v1/chat/completions`

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { ...headers, Authorization: `Bearer ${settings.apiKey}` },
      body: JSON.stringify({
        model: "slm-solana",
        messages: [
          {
            role: "system",
            content:
              "You are an inline code completion engine for Solana/Anchor. Output ONLY the code that continues from <CURSOR>. No markdown, no explanation, no code fences. Just raw code.",
          },
          { role: "user", content: prompt },
        ],
        max_tokens: 128,
        temperature: 0.0,
        stop: ["\n\n", "```"],
        logit_bias: { "18471": -30 },
      }),
      signal,
    })

    if (!response.ok) return null

    const data = (await response.json()) as {
      choices: Array<{ message: { content: string } }>
    }
    const content = data.choices?.[0]?.message?.content?.trim()
    if (!content) return null

    // Clean up: remove any markdown fences the model might add
    let cleaned = content
      .replace(/^```\w*\n?/, "")
      .replace(/\n?```$/, "")
      .trim()

    // Only return if it looks like code (not a sentence)
    if (cleaned.startsWith("Here") || cleaned.startsWith("This")) return null

    return cleaned
  } catch {
    return null
  }
}

/**
 * Register the Sealevel inline completion provider.
 */
export function registerAutocomplete(
  context: vscode.ExtensionContext,
): void {
  const provider: vscode.InlineCompletionItemProvider = {
    async provideInlineCompletionItems(
      document: vscode.TextDocument,
      position: vscode.Position,
      _context: vscode.InlineCompletionContext,
      token: vscode.CancellationToken,
    ): Promise<vscode.InlineCompletionItem[] | null> {
      // Only trigger for supported languages
      if (!SUPPORTED_LANGUAGES.includes(document.languageId)) return null

      // Skip if line is empty (user just hit enter — let them type first)
      const lineText = document.lineAt(position.line).text
      if (lineText.trim().length === 0 && position.character === 0) return null

      // Debounce — wait for user to stop typing
      return new Promise((resolve) => {
        if (debounceTimer) clearTimeout(debounceTimer)

        debounceTimer = setTimeout(async () => {
          if (token.isCancellationRequested) {
            resolve(null)
            return
          }

          const prompt = buildCompletionPrompt(document, position)
          const abortController = new AbortController()
          token.onCancellationRequested(() => abortController.abort())

          const completion = await fetchCompletion(
            prompt,
            abortController.signal,
          )
          if (!completion || token.isCancellationRequested) {
            resolve(null)
            return
          }

          resolve([
            new vscode.InlineCompletionItem(
              completion,
              new vscode.Range(position, position),
            ),
          ])
        }, DEBOUNCE_MS)
      })
    },
  }

  const disposable = vscode.languages.registerInlineCompletionItemProvider(
    SUPPORTED_LANGUAGES.map((lang) => ({ language: lang })),
    provider,
  )

  context.subscriptions.push(disposable)
}
