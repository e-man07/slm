import { getRedis } from "@/lib/redis"
import { resolveUserId } from "@/lib/middleware"
import { generateApiKeyForUser } from "@/lib/db"

/**
 * POST /api/auth/device/verify — Verify a device code (browser-side).
 *
 * User must be authenticated (OAuth session or Bearer token).
 * Links the device code to the user, generates an API key if needed.
 * Body: { code: "XXXX-XXXX" }
 */
export async function POST(request: Request) {
  const userId = await resolveUserId(request)

  if (!userId) {
    return Response.json(
      { error: { code: "unauthorized", message: "Sign in to verify device code", status: 401 } },
      { status: 401 },
    )
  }

  const body = await request.json().catch(() => ({}))
  const code = body.code as string

  if (!code) {
    return Response.json(
      { error: { code: "missing_code", message: "code is required", status: 400 } },
      { status: 400 },
    )
  }

  const redis = getRedis()
  const raw = await redis.get(`device:${code}`)

  if (!raw) {
    return Response.json(
      { error: { code: "not_found", message: "Code expired or invalid", status: 404 } },
      { status: 404 },
    )
  }

  const data = JSON.parse(raw)

  if (data.status === "complete") {
    return Response.json(
      { error: { code: "already_used", message: "Code already used", status: 409 } },
      { status: 409 },
    )
  }

  // Generate API key for user (no-op if they already have one)
  const user = await generateApiKeyForUser(userId)
  if (!user) {
    return Response.json(
      { error: { code: "not_found", message: "User not found", status: 404 } },
      { status: 404 },
    )
  }

  // Update Redis with completed status
  const completed = JSON.stringify({
    status: "complete",
    userId: user.id,
    apiKey: user.apiKey,
    userName: user.name,
    tier: user.tier,
  })

  // Keep 60s TTL for CLI to poll and pick up
  await redis.set(`device:${code}`, completed, "EX", 60)

  return Response.json({ success: true })
}
