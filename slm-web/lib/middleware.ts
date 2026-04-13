import { checkRateLimit, type RateLimitResult } from "./rate-limit"
import { getUserByApiKey } from "./db"
import type { RateLimitTier } from "./constants"

/**
 * Extract API key from the Authorization header.
 * Expects format: "Bearer slm_xxxxx"
 * Returns null if no valid API key is found.
 */
export function extractApiKey(request: Request): string | null {
  const authHeader = request.headers.get("authorization")
  if (!authHeader) return null

  const parts = authHeader.split(" ")
  if (parts.length !== 2 || parts[0] !== "Bearer") return null

  const token = parts[1]
  if (!token.startsWith("slm_")) return null

  return token
}

/**
 * Get the client IP from request headers (supports proxies).
 */
export function getClientIp(request: Request): string {
  return (
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    request.headers.get("x-real-ip") ??
    "unknown"
  )
}

/**
 * Determine the rate limit tier for a request.
 * If the request has a valid API key, look up the user's tier.
 * Otherwise, use "anonymous".
 */
export async function resolveIdentifierAndTier(
  request: Request,
): Promise<{ identifier: string; tier: RateLimitTier; apiKey: string | null }> {
  const apiKey = extractApiKey(request)

  if (apiKey) {
    try {
      const user = await getUserByApiKey(apiKey)
      if (user) {
        return {
          identifier: `key:${apiKey}`,
          tier: user.tier as RateLimitTier,
          apiKey,
        }
      }
    } catch {
      // DB unavailable, fall through to IP-based
    }
  }

  const ip = getClientIp(request)
  return {
    identifier: `ip:${ip}`,
    tier: "anonymous",
    apiKey: null,
  }
}

/**
 * Add rate limit headers to a response.
 */
export function addRateLimitHeaders(
  response: Response,
  result: RateLimitResult,
  limit: number,
): Response {
  response.headers.set("X-RateLimit-Limit", String(limit))
  response.headers.set("X-RateLimit-Remaining", String(result.remaining))
  response.headers.set("X-RateLimit-Reset", String(result.reset))
  return response
}

/**
 * Higher-order function that wraps an API route handler with rate limiting.
 *
 * Usage:
 *   export const POST = withRateLimit(async (request) => { ... })
 */
export function withRateLimit(
  handler: (request: Request) => Promise<Response>,
  endpoint?: string,
): (request: Request) => Promise<Response> {
  return async (request: Request) => {
    const { identifier, tier } = await resolveIdentifierAndTier(request)
    const result = await checkRateLimit(identifier, tier)

    const { RATE_LIMITS } = await import("./constants")
    const limit = RATE_LIMITS[tier].requestsPerMin

    if (!result.allowed) {
      const errorResponse = Response.json(
        {
          error: {
            code: "rate_limit_exceeded",
            message: `Rate limit exceeded. Try again in ${result.reset - Math.floor(Date.now() / 1000)} seconds.`,
            status: 429,
          },
        },
        { status: 429 },
      )
      return addRateLimitHeaders(errorResponse, result, limit)
    }

    const response = await handler(request)
    return addRateLimitHeaders(response, result, limit)
  }
}
