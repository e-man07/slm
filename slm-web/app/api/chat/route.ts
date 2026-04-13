import { SYSTEM_PROMPT, API_URLS } from "@/lib/constants"
import { withRateLimit } from "@/lib/middleware"

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

    // Inject system prompt if not already present
    const hasSystem = messages[0]?.role === "system"
    const fullMessages = hasSystem
      ? messages
      : [{ role: "system", content: SYSTEM_PROMPT }, ...messages]

    const sglangUrl = `${API_URLS.SGLANG_BASE}${API_URLS.CHAT}`

    const response = await fetch(sglangUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "slm-solana",
        messages: fullMessages,
        stream,
        max_tokens,
        temperature,
      }),
    })

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
      // Forward the SSE stream directly
      return new Response(response.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      })
    }

    // Non-streaming response
    const data = await response.json()
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
