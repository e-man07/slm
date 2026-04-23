import { resolveUserId } from "@/lib/middleware"
import { addChatMessage, getChatSession } from "@/lib/db"

/**
 * POST /api/sessions/:id/messages — append a message to the session.
 * Body: { role: "user" | "assistant" | "system", content: string }
 * Supports Bearer token (CLI) and NextAuth session (web).
 */
export async function POST(
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

  // Verify ownership
  const chat = await getChatSession(id, userId)
  if (!chat) {
    return Response.json(
      { error: { code: "not_found", message: "Session not found", status: 404 } },
      { status: 404 },
    )
  }

  const body = await request.json().catch(() => ({}))
  const { role, content } = body
  if (
    (role !== "user" && role !== "assistant" && role !== "system") ||
    typeof content !== "string" ||
    !content.trim()
  ) {
    return Response.json(
      {
        error: {
          code: "invalid_input",
          message: "role must be user|assistant|system and content required",
          status: 400,
        },
      },
      { status: 400 },
    )
  }

  const message = await addChatMessage(id, role, content)
  return Response.json({ message }, { status: 201 })
}
