import { getRedis } from "@/lib/redis"

/**
 * GET /api/auth/device/poll?code=XXXX-XXXX — Poll for device auth completion.
 *
 * CLI calls this every 5 seconds after initiating device flow.
 * Returns { status: "pending" } or { status: "complete", apiKey, user }.
 * Deletes the code from Redis on successful completion (single use).
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const code = url.searchParams.get("code")

  if (!code) {
    return Response.json(
      { error: { code: "missing_code", message: "code query parameter required", status: 400 } },
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

  if (data.status === "pending") {
    return Response.json({ status: "pending" })
  }

  // Complete — return API key and clean up
  await redis.del(`device:${code}`)

  return Response.json({
    status: "complete",
    apiKey: data.apiKey,
    user: {
      name: data.userName,
      tier: data.tier,
    },
  })
}
