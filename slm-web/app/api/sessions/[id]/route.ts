import { auth } from "@/lib/auth-next"
import {
  getChatSession,
  updateChatSession,
  deleteChatSession,
} from "@/lib/db"

/**
 * GET /api/sessions/:id — fetch a session with all messages.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  const session = await auth()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const userId = (session?.user as any)?.userId as number | undefined

  const chat = await getChatSession(id, userId)
  if (!chat) {
    return Response.json(
      { error: { code: "not_found", message: "Session not found", status: 404 } },
      { status: 404 },
    )
  }
  return Response.json({ session: chat })
}

/**
 * PATCH /api/sessions/:id — rename.
 * Body: { title: string }
 */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
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
  if (typeof body.title !== "string" || !body.title.trim()) {
    return Response.json(
      { error: { code: "invalid_input", message: "title required", status: 400 } },
      { status: 400 },
    )
  }

  const result = await updateChatSession(id, userId, body.title.trim())
  if (result.count === 0) {
    return Response.json(
      { error: { code: "not_found", message: "Session not found", status: 404 } },
      { status: 404 },
    )
  }
  return Response.json({ ok: true })
}

/**
 * DELETE /api/sessions/:id
 */
export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  const session = await auth()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const userId = (session?.user as any)?.userId as number | undefined
  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in required", status: 401 } },
      { status: 401 },
    )
  }

  const result = await deleteChatSession(id, userId)
  if (result.count === 0) {
    return Response.json(
      { error: { code: "not_found", message: "Session not found", status: 404 } },
      { status: 404 },
    )
  }
  return Response.json({ ok: true })
}
