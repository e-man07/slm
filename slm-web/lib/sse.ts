export interface TokenTransfer {
  fromUserAccount: string
  toUserAccount: string
  tokenAmount: number
  mint: string
}

export interface TxData {
  status: string
  type: string
  fee: number
  feePayer: string
  blockTime: number
  instructions: unknown[]
  tokenTransfers: TokenTransfer[]
}

export interface LookupResult {
  program_name: string
  error_name: string
  error_message: string
  code: number
  hex: string
}

export type SSEEvent =
  | { type: "chat_delta"; content: string }
  | { type: "tx_data"; data: TxData }
  | { type: "lookup"; data: LookupResult | null }
  | { type: "content"; content: string }
  | { type: "done" }
  | { type: "error"; message: string }

export async function* parseSSEStream(
  response: Response,
): AsyncGenerator<SSEEvent, void, undefined> {
  const body = response.body
  if (!body) {
    yield { type: "error", message: "No response body" }
    return
  }

  const reader = body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += value
      const lines = buffer.split("\n")
      // Keep the last potentially incomplete line in the buffer
      buffer = lines.pop() ?? ""

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith(":")) continue
        if (!trimmed.startsWith("data: ")) continue

        const data = trimmed.slice(6) // Remove "data: "

        if (data === "[DONE]") {
          yield { type: "done" }
          return
        }

        try {
          const parsed = JSON.parse(data)

          // OpenAI-compatible chat format
          if (parsed.choices?.[0]?.delta?.content !== undefined) {
            const content = parsed.choices[0].delta.content
            if (content) {
              yield { type: "chat_delta", content }
            }
            continue
          }

          // Custom explain format with type field
          if (parsed.type === "tx_data") {
            yield { type: "tx_data", data: parsed.data }
            continue
          }

          if (parsed.type === "lookup") {
            yield { type: "lookup", data: parsed.data }
            continue
          }

          if (parsed.type === "content") {
            yield { type: "content", content: parsed.content }
            continue
          }
        } catch {
          yield { type: "error", message: `Failed to parse SSE event: ${data.slice(0, 100)}` }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
