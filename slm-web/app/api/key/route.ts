import { auth } from "@/lib/auth-next"
import { generateApiKeyForUser, rotateApiKey } from "@/lib/db"

/**
 * POST /api/key — generate or rotate API key.
 * Body: { action: "generate" | "rotate" }
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
  const action = body.action as string

  if (action === "generate") {
    const user = await generateApiKeyForUser(userId)
    if (!user) {
      return Response.json(
        { error: { code: "not_found", message: "User not found", status: 404 } },
        { status: 404 },
      )
    }
    return Response.json({ apiKey: user.apiKey })
  }

  if (action === "rotate") {
    const user = await rotateApiKey(userId)
    return Response.json({ apiKey: user.apiKey })
  }

  return Response.json(
    { error: { code: "invalid_input", message: 'action must be "generate" or "rotate"', status: 400 } },
    { status: 400 },
  )
}
