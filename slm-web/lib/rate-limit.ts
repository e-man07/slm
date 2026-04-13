import { getRedis } from "./redis"
import { RATE_LIMITS, type RateLimitTier } from "./constants"

export interface RateLimitResult {
  allowed: boolean
  remaining: number
  reset: number // Unix timestamp when the window resets
}

const WINDOW_MS = 60_000 // 1 minute sliding window

/**
 * Check rate limit for a given identifier and tier using Redis sliding window.
 *
 * Uses a sorted set with timestamps as scores for a sliding window algorithm:
 * 1. Remove entries older than the window
 * 2. Count current entries
 * 3. If under limit, add new entry
 * 4. Set expiry on the key
 */
export async function checkRateLimit(
  identifier: string,
  tier: RateLimitTier,
): Promise<RateLimitResult> {
  const redis = getRedis()
  const limit = RATE_LIMITS[tier].requestsPerMin
  const now = Date.now()
  const windowStart = now - WINDOW_MS
  const key = `ratelimit:${identifier}`

  // Execute atomically with a pipeline
  const pipeline = redis.pipeline()

  // 1. Remove entries outside the window
  pipeline.zremrangebyscore(key, 0, windowStart)

  // 2. Count entries in the window
  pipeline.zcard(key)

  // 3. Add this request
  pipeline.zadd(key, now.toString(), `${now}:${Math.random()}`)

  // 4. Set TTL on the key (auto-cleanup)
  pipeline.pexpire(key, WINDOW_MS)

  const results = await pipeline.exec()

  // results[1] is the zcard result: [error, count]
  const currentCount = (results?.[1]?.[1] as number) ?? 0

  const reset = Math.ceil((now + WINDOW_MS) / 1000)

  if (currentCount >= limit) {
    // Over limit: remove the entry we just added
    // The entry we added is results[2], but we need to undo it
    // Actually, since we already added it before checking, remove the latest
    await redis.zremrangebyscore(key, now, now + 1)

    return {
      allowed: false,
      remaining: 0,
      reset,
    }
  }

  return {
    allowed: true,
    remaining: limit - currentCount - 1,
    reset,
  }
}
