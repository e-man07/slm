import { extractApiKey } from "@/lib/middleware"
import { getUserByApiKey, getUsageStats } from "@/lib/db"

export async function GET(request: Request) {
  const apiKey = extractApiKey(request)

  if (!apiKey) {
    return Response.json(
      {
        error: {
          code: "unauthorized",
          message: "API key required. Include Authorization: Bearer slm_xxx header.",
          status: 401,
        },
      },
      { status: 401 },
    )
  }

  try {
    const user = await getUserByApiKey(apiKey)
    if (!user) {
      return Response.json(
        {
          error: {
            code: "unauthorized",
            message: "Invalid API key.",
            status: 401,
          },
        },
        { status: 401 },
      )
    }

    const stats = await getUsageStats(apiKey, 7)

    // Calculate today's totals
    const today = new Date().toISOString().slice(0, 10)
    const todayStats = stats.find((s) => s.date === today)

    return Response.json({
      user: {
        name: user.name,
        email: user.email,
        tier: user.tier,
        created_at: user.createdAt,
      },
      today: {
        requests: todayStats?.requests ?? 0,
        tokens: todayStats?.tokens ?? 0,
      },
      last_7_days: stats,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error"
    return Response.json(
      { error: { code: "internal_error", message, status: 500 } },
      { status: 500 },
    )
  }
}
