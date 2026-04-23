import { SYSTEM_PROMPT, API_URLS } from "@/lib/constants"
import { fetchEnhancedTransaction } from "@/lib/helius"
import { withRateLimit, resolveCallerForUsage } from "@/lib/middleware"
import { logUsage } from "@/lib/db"

export const POST = withRateLimit(async function POST(request: Request) {
  try {
    const { signature } = await request.json()

    if (!signature || typeof signature !== "string") {
      return Response.json(
        { error: { code: "invalid_input", message: "Transaction signature is required", status: 400 } },
        { status: 400 },
      )
    }

    // Fetch transaction data from Helius
    let txData
    try {
      txData = await fetchEnhancedTransaction(signature)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Helius API error"
      return Response.json(
        { error: { code: "helius_error", message: msg, status: 502 } },
        { status: 502 },
      )
    }

    if (!txData) {
      return Response.json(
        { error: { code: "tx_not_found", message: "Transaction not found", status: 404 } },
        { status: 404 },
      )
    }

    // Build a prompt with the parsed transaction data
    const txSummary = [
      `Transaction: ${signature}`,
      `Type: ${txData.type}`,
      `Description: ${txData.description}`,
      `Fee: ${(txData.fee / 1_000_000_000).toFixed(6)} SOL`,
      `Fee Payer: ${txData.feePayer}`,
      txData.tokenTransfers.length > 0
        ? `Token Transfers: ${txData.tokenTransfers.map((t) => `${t.tokenAmount} of ${t.mint}`).join(", ")}`
        : null,
      txData.nativeTransfers.length > 0
        ? `SOL Transfers: ${txData.nativeTransfers.map((t) => `${(t.amount / 1e9).toFixed(4)} SOL from ${t.fromUserAccount} to ${t.toUserAccount}`).join(", ")}`
        : null,
      `Instructions: ${txData.instructions.length} instruction(s) involving programs: ${[...new Set(txData.instructions.map((i) => i.programId))].join(", ")}`,
    ]
      .filter(Boolean)
      .join("\n")

    const messages = [
      { role: "system", content: SYSTEM_PROMPT },
      {
        role: "user",
        content: `Explain this Solana transaction in simple terms. What did it do and why?\n\n${txSummary}`,
      },
    ]

    // Stream the response
    const sglangUrl = `${API_URLS.SGLANG_BASE}${API_URLS.CHAT}`
    const caller = await resolveCallerForUsage(request)

    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      async start(controller) {
        // First event: structured tx data
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "tx_data", data: { status: "success", type: txData.type, fee: txData.fee / 1e9, feePayer: txData.feePayer, blockTime: txData.timestamp, instructions: txData.instructions, tokenTransfers: txData.tokenTransfers } })}\n\n`,
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
                // Log usage before closing
                if ((caller.userId || caller.apiKey) && totalTokens > 0) {
                  logUsage({ userId: caller.userId, apiKey: caller.apiKey }, "/api/explain/tx", totalTokens, caller.source).catch(() => {})
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
                // Track usage from final chunk
                if (parsed.usage?.total_tokens) {
                  totalTokens = parsed.usage.total_tokens
                }
              } catch {
                // Skip unparseable lines
              }
            }
          }

          // Log usage if stream ended without [DONE]
          if ((caller.userId || caller.apiKey) && totalTokens > 0) {
            logUsage({ userId: caller.userId, apiKey: caller.apiKey }, "/api/explain/tx", totalTokens, caller.source).catch(() => {})
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
}, "explain/tx")
