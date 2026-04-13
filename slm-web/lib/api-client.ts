export interface ChatCompletionOptions {
  messages: Array<{ role: "user" | "assistant" | "system"; content: string }>
  stream?: boolean
  maxTokens?: number
  temperature?: number
  apiKey?: string
}

export interface ExplainTxOptions {
  signature: string
  apiKey?: string
}

export interface DecodeErrorOptions {
  errorCode: string
  programId?: string
  apiKey?: string
}

function buildHeaders(apiKey?: string): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  }
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`
  }
  return headers
}

export function chatCompletions(options: ChatCompletionOptions): Promise<Response> {
  return fetch("/api/chat", {
    method: "POST",
    headers: buildHeaders(options.apiKey),
    body: JSON.stringify({
      messages: options.messages,
      stream: options.stream ?? true,
      max_tokens: options.maxTokens ?? 1024,
      temperature: options.temperature ?? 0.0,
    }),
  })
}

export function explainTransaction(options: ExplainTxOptions): Promise<Response> {
  return fetch("/api/explain/tx", {
    method: "POST",
    headers: buildHeaders(options.apiKey),
    body: JSON.stringify({
      signature: options.signature,
    }),
  })
}

export function decodeError(options: DecodeErrorOptions): Promise<Response> {
  return fetch("/api/explain/error", {
    method: "POST",
    headers: buildHeaders(options.apiKey),
    body: JSON.stringify({
      error_code: options.errorCode,
      program_id: options.programId,
    }),
  })
}
