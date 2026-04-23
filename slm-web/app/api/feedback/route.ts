import { saveFeedback } from "@/lib/db"
import { prisma } from "@/lib/prisma"

export async function POST(request: Request) {
  try {
    const { auth } = await import("@/lib/auth-next")
    const sess = await auth()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const userId = (sess?.user as any)?.userId as number | undefined
    if (!userId) {
      return Response.json(
        { error: { code: "unauthorized", message: "Sign in required", status: 401 } },
        { status: 401 },
      )
    }

    const body = await request.json()
    const { interactionId, responsePrefix, signal } = body

    if (!["up", "down"].includes(signal)) {
      return Response.json(
        { error: { code: "invalid_input", message: "signal (up|down) required", status: 400 } },
        { status: 400 },
      )
    }

    // Look up interaction by ID or by matching the response prefix for this user
    let targetId = interactionId
    if (!targetId && responsePrefix) {
      const match = await prisma.interaction.findFirst({
        where: {
          userId,
          response: { startsWith: responsePrefix.slice(0, 100) },
        },
        orderBy: { createdAt: "desc" },
        select: { id: true },
      })
      targetId = match?.id
    }

    if (!targetId) {
      return Response.json(
        { error: { code: "not_found", message: "Interaction not found", status: 404 } },
        { status: 404 },
      )
    }

    await saveFeedback(targetId, signal)
    return Response.json({ ok: true })
  } catch (error) {
    console.error("Feedback error:", error)
    return Response.json(
      { error: { code: "internal_error", message: "Failed to save feedback", status: 500 } },
      { status: 500 },
    )
  }
}
