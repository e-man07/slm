/**
 * Feature 20: Rate limiting middleware using Redis
 *
 * RED  - tests expect redis client, rate limiter, and middleware exports
 * GREEN - implement lib/redis.ts, lib/rate-limit.ts, lib/middleware.ts
 *
 * Tests use actual Redis on localhost:6379
 */
import { describe, it, expect, afterAll } from "vitest"

// These tests use a real Redis connection on localhost:6379
// We use a test-specific prefix to avoid collisions

describe("Feature 20 - Rate Limiting", () => {
  describe("lib/redis.ts exports", () => {
    it("exports a getRedis function", async () => {
      const { getRedis } = await import("@/lib/redis")
      expect(typeof getRedis).toBe("function")
    })

    it("returns an ioredis instance", async () => {
      const { getRedis } = await import("@/lib/redis")
      const redis = getRedis()
      expect(redis).toBeDefined()
      expect(typeof redis.get).toBe("function")
      expect(typeof redis.set).toBe("function")
      expect(typeof redis.del).toBe("function")
    })
  })

  describe("lib/rate-limit.ts", () => {
    it("exports checkRateLimit function", async () => {
      const { checkRateLimit } = await import("@/lib/rate-limit")
      expect(typeof checkRateLimit).toBe("function")
    })

    it("exports RateLimitResult type shape", async () => {
      const { checkRateLimit } = await import("@/lib/rate-limit")
      // Test with a unique key to not collide
      const testKey = `test:ratelimit:${Date.now()}`
      const result = await checkRateLimit(testKey, "anonymous")
      expect(result).toHaveProperty("allowed")
      expect(result).toHaveProperty("remaining")
      expect(result).toHaveProperty("reset")
      expect(typeof result.allowed).toBe("boolean")
      expect(typeof result.remaining).toBe("number")
      expect(typeof result.reset).toBe("number")
    })

    it("allows requests under the limit", async () => {
      const { checkRateLimit } = await import("@/lib/rate-limit")
      const testKey = `test:ratelimit:under:${Date.now()}`
      const result = await checkRateLimit(testKey, "anonymous")
      expect(result.allowed).toBe(true)
      expect(result.remaining).toBeGreaterThanOrEqual(0)
    })

    it("blocks requests over the limit", async () => {
      const { checkRateLimit } = await import("@/lib/rate-limit")
      const testKey = `test:ratelimit:over:${Date.now()}`
      // Anonymous limit is 5/min, exhaust it
      for (let i = 0; i < 5; i++) {
        await checkRateLimit(testKey, "anonymous")
      }
      const result = await checkRateLimit(testKey, "anonymous")
      expect(result.allowed).toBe(false)
      expect(result.remaining).toBe(0)
    })

    it("different tiers have different limits", async () => {
      const { checkRateLimit } = await import("@/lib/rate-limit")
      const anonKey = `test:ratelimit:anon:${Date.now()}`
      const freeKey = `test:ratelimit:free:${Date.now()}`

      const anonResult = await checkRateLimit(anonKey, "anonymous")
      const freeResult = await checkRateLimit(freeKey, "free")

      // Free tier has higher remaining than anonymous
      expect(freeResult.remaining).toBeGreaterThan(anonResult.remaining)
    })
  })

  describe("lib/middleware.ts", () => {
    it("exports withRateLimit function", async () => {
      const { withRateLimit } = await import("@/lib/middleware")
      expect(typeof withRateLimit).toBe("function")
    })

    it("exports extractApiKey function", async () => {
      const { extractApiKey } = await import("@/lib/middleware")
      expect(typeof extractApiKey).toBe("function")
    })

    it("extractApiKey parses Bearer token from Authorization header", async () => {
      const { extractApiKey } = await import("@/lib/middleware")
      const headers = new Headers({ Authorization: "Bearer slm_abc123" })
      const request = new Request("http://localhost/api/test", { headers })
      expect(extractApiKey(request)).toBe("slm_abc123")
    })

    it("extractApiKey returns null for missing header", async () => {
      const { extractApiKey } = await import("@/lib/middleware")
      const request = new Request("http://localhost/api/test")
      expect(extractApiKey(request)).toBeNull()
    })

    it("extractApiKey returns null for non-slm_ tokens", async () => {
      const { extractApiKey } = await import("@/lib/middleware")
      const headers = new Headers({ Authorization: "Bearer invalid_key" })
      const request = new Request("http://localhost/api/test", { headers })
      expect(extractApiKey(request)).toBeNull()
    })
  })

  // Clean up Redis test keys
  afterAll(async () => {
    const { getRedis } = await import("@/lib/redis")
    const redis = getRedis()
    const keys = await redis.keys("test:ratelimit:*")
    if (keys.length > 0) {
      await redis.del(...keys)
    }
    redis.disconnect()
  })
})
