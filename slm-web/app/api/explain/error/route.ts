import { SYSTEM_PROMPT, API_URLS } from "@/lib/constants"
import { lookupError } from "@/lib/errors"
import { withRateLimit, resolveCallerForUsage } from "@/lib/middleware"
import { logUsage } from "@/lib/db"

export const POST = withRateLimit(async function POST(request: Request) {
  try {
    const { error_code, program_id } = await request.json()

    if (!error_code) {
      return Response.json(
        { error: { code: "invalid_input", message: "Error code is required", status: 400 } },
        { status: 400 },
      )
    }

    // Look up the error in the static table
    const lookupResult = lookupError(error_code, program_id)

    // Build prompt for LLM explanation
    const errorContext = lookupResult
      ? `Program: ${lookupResult.program_name}\nError: ${lookupResult.error_name} (${lookupResult.hex})\nMessage: ${lookupResult.error_message}`
      : `Unknown error code: ${error_code}${program_id ? ` for program ${program_id}` : ""}`

    const messages = [
      { role: "system", content: SYSTEM_PROMPT },
      {
        role: "user",
        content: `Explain this Solana program error and how to fix it:\n\n${errorContext}\n\nProvide a clear explanation of what causes this error and show a code example of how to fix it.`,
      },
    ]

    const sglangUrl = `${API_URLS.SGLANG_BASE}${API_URLS.CHAT}`
    const caller = await resolveCallerForUsage(request)
    const encoder = new TextEncoder()

    const stream = new ReadableStream({
      async start(controller) {
        // First event: lookup result
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "lookup", data: lookupResult })}\n\n`,
          ),
        )

        // Then stream LLM explanation
        try {
          const llmResponse = await fetch(sglangUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              model: "slm-solana",
              messages,
              stream: true,
              max_tokens: 1024,
              temperature: 0.0,
              stream_options: { include_usage: true },
            }),
            signal: AbortSignal.timeout(9000),
          })

          if (!llmResponse.ok || !llmResponse.body) {
            controller.enqueue(
              encoder.encode(
                `data: ${JSON.stringify({ type: "content", content: "Unable to generate AI explanation at this time." })}\n\n`,
              ),
            )
            controller.enqueue(encoder.encode("data: [DONE]\n\n"))
            controller.close()
            return
          }

          const reader = llmResponse.body.pipeThrough(new TextDecoderStream()).getReader()
          let buffer = ""
          let totalTokens = 0

          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += value
            const lines = buffer.split("\n")
            buffer = lines.pop() ?? ""

            for (const line of lines) {
              const trimmed = line.trim()
              if (!trimmed.startsWith("data: ")) continue

              const data = trimmed.slice(6)
              if (data === "[DONE]") {
                if ((caller.userId || caller.apiKey) && totalTokens > 0) {
                  logUsage({ userId: caller.userId, apiKey: caller.apiKey }, "/api/explain/error", totalTokens, caller.source).catch(() => {})
                }
                controller.enqueue(encoder.encode("data: [DONE]\n\n"))
                controller.close()
                return
              }

              try {
                const parsed = JSON.parse(data)
                const content = parsed.choices?.[0]?.delta?.content
                if (content) {
                  controller.enqueue(
                    encoder.encode(
                      `data: ${JSON.stringify({ type: "content", content })}\n\n`,
                    ),
                  )
                }
                if (parsed.usage?.total_tokens) {
                  totalTokens = parsed.usage.total_tokens
                }
              } catch {
                // Skip
              }
            }
          }

          if ((caller.userId || caller.apiKey) && totalTokens > 0) {
            logUsage({ userId: caller.userId, apiKey: caller.apiKey }, "/api/explain/error", totalTokens, caller.source).catch(() => {})
          }
          controller.enqueue(encoder.encode("data: [DONE]\n\n"))
          controller.close()
        } catch {
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({ type: "content", content: "Unable to connect to the AI model for explanation." })}\n\n`,
            ),
          )
          controller.enqueue(encoder.encode("data: [DONE]\n\n"))
          controller.close()
        }
      },
    })

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error"
    return Response.json(
      { error: { code: "internal_error", message, status: 500 } },
      { status: 500 },
    )
  }
}, "explain/error")
