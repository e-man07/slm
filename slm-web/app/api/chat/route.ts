import { SYSTEM_PROMPT, API_URLS, MAX_TOKENS_CAP, MAX_MESSAGES, MAX_MESSAGE_LENGTH } from "@/lib/constants"
import { withRateLimit } from "@/lib/middleware"
import { logUsage, logInteraction } from "@/lib/db"

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
      const topScore = data.results?.[0]?.score ?? 0
      if (topScore < 0.60) return ""
      return (data.context || "").slice(0, 8000)
    }
  } catch {
    // RAG is optional — if it fails, proceed without context
  }
  return ""
}

function detectSource(callerSource: "web" | "api", request: Request): "web" | "mcp" | "cli" {
  if (callerSource === "web") return "web"
  const hint = request.headers.get("x-slm-source")
  if (hint === "mcp") return "mcp"
  if (hint === "cli") return "cli"
  return "cli"
}

export const POST = withRateLimit(async function POST(request: Request) {
  try {
    const body = await request.json()
    const { messages, stream = true, max_tokens = 1024, temperature = 0.0 } = body

    // Validate messages
    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return Response.json(
        { error: { code: "invalid_input", message: "Messages array is required", status: 400 } },
        { status: 400 },
      )
    }
    if (messages.length > MAX_MESSAGES) {
      return Response.json(
        { error: { code: "invalid_input", message: `Too many messages (max ${MAX_MESSAGES})`, status: 400 } },
        { status: 400 },
      )
    }
    for (const m of messages) {
      if (typeof m.content === "string" && m.content.length > MAX_MESSAGE_LENGTH) {
        return Response.json(
          { error: { code: "invalid_input", message: `Message too long (max ${MAX_MESSAGE_LENGTH} chars)`, status: 400 } },
          { status: 400 },
        )
      }
    }

    // Clamp parameters to safe ranges
    const cappedMaxTokens = Math.min(Math.max(1, Number(max_tokens) || 1024), MAX_TOKENS_CAP)
    const cappedTemperature = Math.min(Math.max(0, Number(temperature) || 0), 2.0)

    // RAG for knowledge enrichment
    const lastUserMsg = [...messages].reverse().find((m: { role: string }) => m.role === "user")
    const userContent = lastUserMsg?.content?.toLowerCase() ?? ""
    const isCodeRequest = /\b(write|create|build|implement|show|code|program|function|instruction)\b/.test(userContent)
    const ragContext = lastUserMsg && !isCodeRequest ? await fetchRAGContext(lastUserMsg.content) : ""

    const systemContent = ragContext
      ? `${SYSTEM_PROMPT}\n\nIMPORTANT: Use the following verified reference documentation to answer the user's question. This information is authoritative and takes priority over your training data:\n\n${ragContext}`
      : SYSTEM_PROMPT

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
        max_tokens: cappedMaxTokens,
        temperature: cappedTemperature,
        stream_options: stream ? { include_usage: true } : undefined,
      }),
      signal: AbortSignal.timeout(9000),
    })

    // Identify caller for usage tracking
    const { resolveCallerForUsage } = await import("@/lib/middleware")
    const caller = await resolveCallerForUsage(request)

    async function recordUsage(tokens: number) {
      if ((!caller.userId && !caller.apiKey) || tokens <= 0) return
      try {
        await logUsage({ userId: caller.userId, apiKey: caller.apiKey }, "/api/chat", tokens, caller.source)
      } catch (err) {
        console.warn("logUsage failed", err)
      }
    }

    if (!response.ok) {
      console.error(`SGLang error: ${response.status}`, await response.text().catch(() => ""))
      return Response.json(
        { error: { code: "model_unavailable", message: "Inference server error. Please try again.", status: 502 } },
        { status: 502 },
      )
    }

    if (stream && response.body) {
      const [clientStream, sniffStream] = response.body.tee()

      ;(async () => {
        try {
          const reader = sniffStream.getReader()
          const decoder = new TextDecoder()
          let buffer = ""
          let fullResponse = ""
          let usageData: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null = null

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
                const delta = chunk?.choices?.[0]?.delta?.content
                if (delta) fullResponse += delta
                if (chunk?.usage?.total_tokens) usageData = chunk.usage
              } catch {
                // Ignore malformed chunks
              }
            }
          }

          if (usageData?.total_tokens) await recordUsage(usageData.total_tokens)

          // Log interaction for retraining data collection
          if (fullResponse && caller.userId) {
            logInteraction({
              userId: caller.userId,
              source: detectSource(caller.source, request),
              promptMessages: JSON.stringify(messages),
              response: fullResponse,
              promptTokens: usageData?.prompt_tokens ?? 0,
              completionTokens: usageData?.completion_tokens ?? 0,
              totalTokens: usageData?.total_tokens ?? 0,
              ragContext: ragContext || null,
            }).catch(() => {})
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

    const data = await response.json()
    if (data?.usage?.total_tokens) {
      void recordUsage(data.usage.total_tokens)
    }
    // Log interaction for non-streaming responses
    const assistantContent = data?.choices?.[0]?.message?.content ?? ""
    if (assistantContent && caller.userId) {
      logInteraction({
        userId: caller.userId,
        source: detectSource(caller.source, request),
        promptMessages: JSON.stringify(messages),
        response: assistantContent,
        promptTokens: data?.usage?.prompt_tokens ?? 0,
        completionTokens: data?.usage?.completion_tokens ?? 0,
        totalTokens: data?.usage?.total_tokens ?? 0,
        ragContext: ragContext || null,
      }).catch(() => {})
    }
    return Response.json(data)
  } catch (error) {
    console.error("Chat route error:", error)
    const isConnectionError = error instanceof Error &&
      (error.message.includes("ECONNREFUSED") || error.message.includes("fetch failed") || error.message.includes("AbortError"))

    return Response.json(
      {
        error: {
          code: isConnectionError ? "model_unavailable" : "internal_error",
          message: isConnectionError
            ? "Model inference server is not available. Please try again later."
            : "An internal error occurred. Please try again.",
          status: isConnectionError ? 503 : 500,
        },
      },
      { status: isConnectionError ? 503 : 500 },
    )
  }
}, "chat")
