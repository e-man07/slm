import { resolveUserId, withRateLimit } from "@/lib/middleware"
import { logUsage } from "@/lib/db"

/**
 * POST /api/agent — Proxy for agent tool-calling LLM.
 *
 * CLI sends tool-calling requests here. Backend forwards to the
 * agent model server. User authenticates with their Sealevel API key.
 * Agent model URL/key stay server-side only (Vercel env vars).
 */
export const POST = withRateLimit(async (request: Request) => {
  const userId = await resolveUserId(request)

  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in or provide API key", status: 401 } },
      { status: 401 },
    )
  }

  const body = await request.json().catch(() => ({}))

  // Validate request
  const messages = body.messages ?? []
  if (!Array.isArray(messages) || messages.length === 0) {
    return Response.json(
      { error: { code: "invalid_input", message: "messages array required", status: 400 } },
      { status: 400 },
    )
  }
  if (messages.length > 100) {
    return Response.json(
      { error: { code: "invalid_input", message: "Too many messages (max 100)", status: 400 } },
      { status: 400 },
    )
  }

  // Agent model config from server-side env vars
  const agentUrl = process.env.AGENT_LLM_URL ?? ""
  const agentKey = process.env.AGENT_LLM_KEY ?? ""
  const agentModel = process.env.AGENT_LLM_MODEL ?? "default"

  if (!agentUrl) {
    return Response.json(
      { error: { code: "not_configured", message: "Agent model not configured", status: 503 } },
      { status: 503 },
    )
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 120_000) // 2 min timeout

  try {
    const resp = await fetch(agentUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${agentKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: agentModel,
        messages,
        tools: body.tools ?? [],
        tool_choice: body.tool_choice ?? "auto",
        max_tokens: Math.min(body.max_tokens ?? 4096, 8192),
        temperature: body.temperature ?? 0.0,
      }),
      signal: controller.signal,
    })

    clearTimeout(timeout)

    if (!resp.ok) {
      return Response.json(
        { error: { code: "agent_error", message: `Agent model error: ${resp.status}`, status: resp.status } },
        { status: resp.status },
      )
    }

    const data = await resp.json()

    // Log usage
    const usage = data.usage ?? {}
    const tokensUsed = usage.total_tokens ?? 0
    if (tokensUsed > 0) {
      await logUsage({ userId }, "/api/agent", tokensUsed, "api").catch(() => {})
    }

    return Response.json(data)
  } catch (err) {
    clearTimeout(timeout)
    if ((err as Error).name === "AbortError") {
      return Response.json(
        { error: { code: "timeout", message: "Agent model timed out", status: 504 } },
        { status: 504 },
      )
    }
    return Response.json(
      { error: { code: "agent_error", message: "Agent model unreachable", status: 502 } },
      { status: 502 },
    )
  }
}, "/api/agent")
