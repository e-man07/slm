import { checkRateLimit, type RateLimitResult } from "./rate-limit"
import { getUserByApiKey, getTodayTokensByUserId } from "./db"
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
 * Resolve the caller's userId, apiKey, and source (web vs api).
 * Bearer token → API caller. NextAuth session → web caller.
 */
export async function resolveCallerForUsage(
  request: Request,
): Promise<{ userId: number | null; apiKey: string | null; source: "web" | "api" }> {
  const bearerKey = extractApiKey(request)
  if (bearerKey) {
    try {
      const user = await getUserByApiKey(bearerKey)
      return { userId: user?.id ?? null, apiKey: bearerKey, source: "api" }
    } catch {
      return { userId: null, apiKey: bearerKey, source: "api" }
    }
  }

  try {
    const { auth } = await import("./auth-next")
    const sess = await auth()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const user = sess?.user as any
    if (user?.userId) {
      return { userId: user.userId, apiKey: null, source: "web" }
    }
  } catch {
    // Session unavailable
  }

  return { userId: null, apiKey: null, source: "web" }
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
 * Checks API key first, then NextAuth session, then falls back to IP-based anonymous.
 */
export async function resolveIdentifierAndTier(
  request: Request,
): Promise<{ identifier: string; tier: RateLimitTier; userId: number | null; apiKey: string | null }> {
  const apiKey = extractApiKey(request)

  if (apiKey) {
    try {
      const user = await getUserByApiKey(apiKey)
      if (user) {
        return {
          identifier: `key:${apiKey}`,
          tier: user.tier as RateLimitTier,
          userId: user.id,
          apiKey,
        }
      }
    } catch {
      // DB unavailable, fall through
    }
  }

  // Check NextAuth session for web users — give them their tier, not anonymous
  try {
    const { auth } = await import("./auth-next")
    const sess = await auth()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const user = sess?.user as any
    if (user?.userId) {
      return {
        identifier: `user:${user.userId}`,
        tier: (user.tier as RateLimitTier) ?? "free",
        userId: user.userId,
        apiKey: null,
      }
    }
  } catch {
    // Session unavailable, fall through to IP-based
  }

  const ip = getClientIp(request)
  return {
    identifier: `ip:${ip}`,
    tier: "anonymous",
    userId: null,
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
 * Check daily token budget by userId (combined web + API).
 * Returns null if within budget, or an error Response if over.
 */
async function checkDailyTokenBudget(
  userId: number | null,
  tier: RateLimitTier,
): Promise<Response | null> {
  if (!userId || tier === "admin") return null

  const { RATE_LIMITS } = await import("./constants")
  const dailyLimit = RATE_LIMITS[tier].tokensPerDay
  if (dailyLimit === Infinity) return null

  try {
    const tokensUsed = await getTodayTokensByUserId(userId)

    if (tokensUsed >= dailyLimit) {
      return Response.json(
        {
          error: {
            code: "daily_token_limit_exceeded",
            message: `Daily token limit exceeded (${tokensUsed.toLocaleString()} / ${dailyLimit.toLocaleString()} tokens). Resets at midnight UTC.`,
            status: 429,
          },
        },
        { status: 429 },
      )
    }
  } catch {
    // DB unavailable — allow request rather than block
  }

  return null
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
    const { identifier, tier, userId } = await resolveIdentifierAndTier(request)

    // Require authentication — no anonymous access
    if (tier === "anonymous") {
      return Response.json(
        {
          error: {
            code: "unauthorized",
            message: "Sign in or provide an API key. Get one at sealevel.tech/dashboard",
            status: 401,
          },
        },
        { status: 401 },
      )
    }

    // Check per-minute request limit
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

    // Check daily token budget (combined across web + API)
    const tokenBudgetError = await checkDailyTokenBudget(userId, tier)
    if (tokenBudgetError) {
      return addRateLimitHeaders(tokenBudgetError, result, limit)
    }

    const response = await handler(request)
    return addRateLimitHeaders(response, result, limit)
  }
}
