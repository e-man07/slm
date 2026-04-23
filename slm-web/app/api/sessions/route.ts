import { resolveUserId } from "@/lib/middleware"
import { createChatSession, listChatSessions } from "@/lib/db"

/**
 * GET /api/sessions — list current user's chat sessions (most recent first).
 * Supports Bearer token (CLI) and NextAuth session (web).
 */
export async function GET(request: Request) {
  const userId = await resolveUserId(request)
  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in or provide API key", status: 401 } },
      { status: 401 },
    )
  }

  const url = new URL(request.url)
  const source = url.searchParams.get("source") ?? undefined
  const sessions = await listChatSessions(userId, source)
  return Response.json({ sessions })
}

/**
 * POST /api/sessions — create a new chat session.
 * Body: { title?: string }
 */
export async function POST(request: Request) {
  const userId = await resolveUserId(request)
  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in or provide API key", status: 401 } },
      { status: 401 },
    )
  }

  const body = await request.json().catch(() => ({}))
  const title = typeof body.title === "string" && body.title.trim() ? body.title.trim() : "New chat"
  const source = typeof body.source === "string" && ["web", "cli", "mcp"].includes(body.source) ? body.source : "web"
  const created = await createChatSession(userId, title, source)
  return Response.json({ session: created }, { status: 201 })
}
