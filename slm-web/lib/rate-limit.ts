import { getRedis } from "./redis"
import { RATE_LIMITS, type RateLimitTier } from "./constants"

export interface RateLimitResult {
  allowed: boolean
  remaining: number
  reset: number // Unix timestamp when the window resets
}

const WINDOW_MS = 60_000 // 1 minute sliding window

// ── In-memory fallback (used when Redis is unavailable) ──

const inMemoryWindows = new Map<string, number[]>()

// Periodic cleanup to prevent memory leaks in long-running processes
if (typeof setInterval !== "undefined") {
  setInterval(() => {
    const cutoff = Date.now() - WINDOW_MS
    for (const [key, timestamps] of inMemoryWindows) {
      const filtered = timestamps.filter((t) => t > cutoff)
      if (filtered.length === 0) inMemoryWindows.delete(key)
      else inMemoryWindows.set(key, filtered)
    }
  }, 60_000)
}

function checkRateLimitInMemory(
  identifier: string,
  limit: number,
): RateLimitResult {
  const now = Date.now()
  const windowStart = now - WINDOW_MS
  let timestamps = inMemoryWindows.get(identifier) ?? []
  timestamps = timestamps.filter((t) => t > windowStart)

  const reset = Math.ceil((now + WINDOW_MS) / 1000)

  if (timestamps.length >= limit) {
    inMemoryWindows.set(identifier, timestamps)
    return { allowed: false, remaining: 0, reset }
  }

  timestamps.push(now)
  inMemoryWindows.set(identifier, timestamps)
  return { allowed: true, remaining: limit - timestamps.length, reset }
}

// ── Main rate limiter (Redis primary, in-memory fallback) ──

export async function checkRateLimit(
  identifier: string,
  tier: RateLimitTier,
): Promise<RateLimitResult> {
  const limit = RATE_LIMITS[tier].requestsPerMin

  try {
    const redis = getRedis()
    const now = Date.now()
    const windowStart = now - WINDOW_MS
    const key = `ratelimit:${identifier}`

    const pipeline = redis.pipeline()
    pipeline.zremrangebyscore(key, 0, windowStart)
    pipeline.zcard(key)
    pipeline.zadd(key, now.toString(), `${now}:${Math.random()}`)
    pipeline.pexpire(key, WINDOW_MS)

    const results = await pipeline.exec()
    const currentCount = (results?.[1]?.[1] as number) ?? 0
    const reset = Math.ceil((now + WINDOW_MS) / 1000)

    if (currentCount >= limit) {
      await redis.zremrangebyscore(key, now, now + 1)
      return { allowed: false, remaining: 0, reset }
    }

    return {
      allowed: true,
      remaining: limit - currentCount - 1,
      reset,
    }
  } catch {
    // Redis unavailable — fall back to in-memory rate limiting
    return checkRateLimitInMemory(identifier, limit)
  }
}
