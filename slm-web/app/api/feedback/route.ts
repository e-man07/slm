import { saveFeedback } from "@/lib/db"

export async function POST(request: Request) {
  try {
    const { auth } = await import("@/lib/auth-next")
    const sess = await auth()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const userId = (sess?.user as any)?.userId
    if (!userId) {
      return Response.json(
        { error: { code: "unauthorized", message: "Sign in required", status: 401 } },
        { status: 401 },
      )
    }

    const body = await request.json()
    const { interactionId, signal } = body

    if (!interactionId || !["up", "down"].includes(signal)) {
      return Response.json(
        { error: { code: "invalid_input", message: "interactionId and signal (up|down) required", status: 400 } },
        { status: 400 },
      )
    }

    await saveFeedback(interactionId, signal)
    return Response.json({ ok: true })
  } catch (error) {
    console.error("Feedback error:", error)
    return Response.json(
      { error: { code: "internal_error", message: "Failed to save feedback", status: 500 } },
      { status: 500 },
    )
  }
}
