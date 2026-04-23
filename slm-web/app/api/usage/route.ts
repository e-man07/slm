import { extractApiKey } from "@/lib/middleware"
import { getUserByApiKey, getUsageStats } from "@/lib/db"

export async function GET(request: Request) {
  let userId: number | null = null
  let tier = "free"

  // 1. Try Bearer token (API caller checking usage)
  const bearerKey = extractApiKey(request)
  if (bearerKey) {
    const user = await getUserByApiKey(bearerKey)
    if (!user) {
      return Response.json(
        { error: { code: "unauthorized", message: "Invalid API key.", status: 401 } },
        { status: 401 },
      )
    }
    userId = user.id
    tier = user.tier
  }

  // 2. Fall back to NextAuth session (web user on dashboard)
  if (!userId) {
    try {
      const { auth } = await import("@/lib/auth-next")
      const sess = await auth()
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const sessionUser = sess?.user as any
      if (sessionUser?.userId) {
        userId = sessionUser.userId
        tier = sessionUser.tier ?? "free"
      }
    } catch {
      // Session unavailable
    }
  }

  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in or provide API key.", status: 401 } },
      { status: 401 },
    )
  }

  try {
    const { daily, endpoints, web, api } = await getUsageStats(userId, 7)

    const today = new Date().toISOString().slice(0, 10)
    const todayStats = daily.find((s) => s.date === today)

    return Response.json({
      user: { tier },
      today: {
        requests: todayStats?.requests ?? 0,
        tokens: todayStats?.tokens ?? 0,
      },
      last_7_days: daily,
      by_endpoint: endpoints,
      by_source: { web, api },
    })
  } catch (error) {
    console.error("Usage route error:", error)
    return Response.json(
      { error: { code: "internal_error", message: "Failed to fetch usage stats", status: 500 } },
      { status: 500 },
    )
  }
}
