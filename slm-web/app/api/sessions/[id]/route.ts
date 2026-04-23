import { resolveUserId } from "@/lib/middleware"
import {
  getChatSession,
  updateChatSession,
  deleteChatSession,
} from "@/lib/db"

/**
 * GET /api/sessions/:id — fetch a session with all messages.
 * Supports Bearer token (CLI) and NextAuth session (web).
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  const userId = await resolveUserId(request)

  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in or provide API key", status: 401 } },
      { status: 401 },
    )
  }

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
  const userId = await resolveUserId(request)
  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in or provide API key", status: 401 } },
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
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  const userId = await resolveUserId(request)
  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in or provide API key", status: 401 } },
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
