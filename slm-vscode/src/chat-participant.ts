import * as vscode from "vscode"
import { getSettings, buildHeaders } from "./settings"

export const PARTICIPANT_ID = "slm.chat"

interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string
}

interface ChatPayload {
  messages: ChatMessage[]
  stream: boolean
  max_tokens: number
  temperature: number
}

/**
 * Format a chat payload for the Sealevel API.
 */
export function formatChatPayload(
  message: string,
  history?: ChatMessage[],
): ChatPayload {
  const messages: ChatMessage[] = []
  if (history) {
    messages.push(...history)
  }
  messages.push({ role: "user", content: message })

  return {
    messages,
    stream: true,
    max_tokens: 1024,
    temperature: 0.0,
  }
}

/**
 * Parse an SSE chunk line and extract content.
 * Returns the content string or null if no content.
 */
export function parseSseChunk(line: string): string | null {
  if (!line.startsWith("data: ")) {
    return null
  }

  const data = line.slice(6).trim()
  if (data === "[DONE]") {
    return null
  }

  try {
    const parsed = JSON.parse(data)

    // Handle OpenAI-style delta format
    if (parsed.choices?.[0]?.delta?.content) {
      return parsed.choices[0].delta.content
    }

    // Handle direct content format
    if (parsed.type === "content" && parsed.content) {
      return parsed.content
    }

    return null
  } catch {
    return null
  }
}

/**
 * Register the Sealevel chat participant with VS Code.
 */
export function registerChatParticipant(
  context: vscode.ExtensionContext,
): void {
  const participant = vscode.chat.createChatParticipant(
    PARTICIPANT_ID,
    async (
      request: vscode.ChatRequest,
      _context: vscode.ChatContext,
      stream: vscode.ChatResponseStream,
      token: vscode.CancellationToken,
    ) => {
      const settings = getSettings()
      const headers = buildHeaders(settings.apiKey)
      const payload = formatChatPayload(request.prompt)

      try {
        const response = await fetch(`${settings.apiUrl}/chat`, {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
        })

        if (!response.ok || !response.body) {
          stream.markdown(
            `**Error:** API returned status ${response.status}. Check your API key in settings.`,
          )
          return
        }

        const reader = response.body
          .pipeThrough(new TextDecoderStream())
          .getReader()
        let buffer = ""

        while (!token.isCancellationRequested) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += value
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""

          for (const line of lines) {
            const content = parseSseChunk(line.trim())
            if (content) {
              stream.markdown(content)
            }
          }
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unknown error"
        stream.markdown(
          `**Error:** Could not connect to Sealevel API. ${message}`,
        )
      }
    },
  )

  context.subscriptions.push(participant)
}
