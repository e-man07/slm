import { SYSTEM_PROMPT, API_URLS } from "@/lib/constants"
import { withRateLimit } from "@/lib/middleware"
import { logUsage } from "@/lib/db"

async function fetchRAGContext(query: string): Promise<string> {
  try {
    const ragUrl = `${API_URLS.RAG_BASE}${API_URLS.RAG_QUERY}`
    const resp = await fetch(ragUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: 5 }),
      signal: AbortSignal.timeout(5000),
    })
    if (resp.ok) {
      const data = await resp.json()
      // Only inject RAG if top result is highly relevant (>0.80)
      const topScore = data.results?.[0]?.score ?? 0
      if (topScore < 0.80) return ""
      return data.context || ""
    }
  } catch {
    // RAG is optional — if it fails, proceed without context
  }
  return ""
}

export const POST = withRateLimit(async function POST(request: Request) {
  try {
    const body = await request.json()
    const { messages, stream = true, max_tokens = 1024, temperature = 0.0 } = body

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return Response.json(
        { error: { code: "invalid_input", message: "Messages array is required", status: 400 } },
        { status: 400 },
      )
    }

    // RAG for knowledge enrichment — supplements model knowledge, never restricts it
    const lastUserMsg = [...messages].reverse().find((m: { role: string }) => m.role === "user")
    const userContent = lastUserMsg?.content?.toLowerCase() ?? ""
    const isCodeRequest = /\b(write|create|build|implement|show|code|program|function|instruction)\b/.test(userContent)
    const ragContext = lastUserMsg && !isCodeRequest ? await fetchRAGContext(lastUserMsg.content) : ""

    const systemContent = ragContext
      ? `${SYSTEM_PROMPT}\n\nYou also have access to these reference docs for additional context. Always answer from your full knowledge first, then supplement with these if relevant:\n\n${ragContext}`
      : SYSTEM_PROMPT

    // Inject system prompt if not already present
    const hasSystem = messages[0]?.role === "system"
    const fullMessages = hasSystem
      ? messages
      : [{ role: "system", content: systemContent }, ...messages]

    const sglangUrl = `${API_URLS.SGLANG_BASE}${API_URLS.CHAT}`

    const sglangHeaders: Record<string, string> = { "Content-Type": "application/json" }
    if (process.env.SGLANG_API_KEY) {
      sglangHeaders["Authorization"] = `Bearer ${process.env.SGLANG_API_KEY}`
    }

    const response = await fetch(sglangUrl, {
      method: "POST",
      headers: sglangHeaders,
      body: JSON.stringify({
        model: "slm-solana",
        messages: fullMessages,
        stream,
        max_tokens,
        temperature,
        // Ask LiteLLM/SGLang to include usage stats in the final SSE chunk
        stream_options: stream ? { include_usage: true } : undefined,
      }),
    })

    // Identify caller for usage tracking
    const authHeader = request.headers.get("Authorization") ?? ""
    const callerApiKey = authHeader.startsWith("Bearer ")
      ? authHeader.slice(7).trim()
      : "anonymous"

    async function recordUsage(tokens: number) {
      if (callerApiKey === "anonymous" || tokens <= 0) return
      try {
        await logUsage(callerApiKey, "/api/chat", tokens)
      } catch (err) {
        console.warn("logUsage failed", err)
      }
    }

    if (!response.ok) {
      const errorText = await response.text().catch(() => "Unknown error")
      return Response.json(
        {
          error: {
            code: "model_unavailable",
            message: `Inference server error: ${response.status}`,
            details: errorText,
            status: 502,
          },
        },
        { status: 502 },
      )
    }

    if (stream && response.body) {
      // Tee the stream: one branch to client, one to a token-usage sniffer
      const [clientStream, sniffStream] = response.body.tee()

      // Background task: read sniff stream, find final `usage` chunk, log tokens
      ;(async () => {
        try {
          const reader = sniffStream.getReader()
          const decoder = new TextDecoder()
          let buffer = ""
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split("\n")
            buffer = lines.pop() ?? ""
            for (const line of lines) {
              if (!line.startsWith("data: ") || line.endsWith("[DONE]")) continue
              try {
                const chunk = JSON.parse(line.slice(6))
                const usage = chunk?.usage
                if (usage?.total_tokens) {
                  await recordUsage(usage.total_tokens)
                  return
                }
              } catch {
                // Ignore malformed chunks
              }
            }
          }
        } catch {
          // Sniffer errors are non-fatal
        }
      })()

      return new Response(clientStream, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      })
    }

    // Non-streaming response — grab usage directly
    const data = await response.json()
    if (data?.usage?.total_tokens) {
      void recordUsage(data.usage.total_tokens)
    }
    return Response.json(data)
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error"

    // Check if it's a connection error (SGLang not running)
    if (message.includes("ECONNREFUSED") || message.includes("fetch failed")) {
      return Response.json(
        {
          error: {
            code: "model_unavailable",
            message: "Model inference server is not available. Please try again later.",
            status: 503,
          },
        },
        { status: 503 },
      )
    }

    return Response.json(
      { error: { code: "internal_error", message, status: 500 } },
      { status: 500 },
    )
  }
}, "chat")
