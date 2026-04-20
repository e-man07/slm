import { auth } from "@/lib/auth-next"
import { createChatSession, listChatSessions } from "@/lib/db"

/**
 * GET /api/sessions — list current user's chat sessions (most recent first).
 */
export async function GET() {
  const session = await auth()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const userId = (session?.user as any)?.userId as number | undefined
  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in required", status: 401 } },
      { status: 401 },
    )
  }

  const sessions = await listChatSessions(userId)
  return Response.json({ sessions })
}

/**
 * POST /api/sessions — create a new chat session.
 * Body: { title?: string }
 */
export async function POST(request: Request) {
  const session = await auth()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const userId = (session?.user as any)?.userId as number | undefined
  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in required", status: 401 } },
      { status: 401 },
    )
  }

  const body = await request.json().catch(() => ({}))
  const title = typeof body.title === "string" && body.title.trim() ? body.title.trim() : "New chat"
  const created = await createChatSession(userId, title)
  return Response.json({ session: created }, { status: 201 })
}
