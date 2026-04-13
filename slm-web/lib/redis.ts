import Redis from "ioredis"

let redisInstance: Redis | null = null

/**
 * Get a singleton Redis client.
 * Connects to REDIS_URL or defaults to localhost:6379.
 */
export function getRedis(): Redis {
  if (!redisInstance) {
    const url = process.env.REDIS_URL ?? "redis://localhost:6379"
    redisInstance = new Redis(url, {
      maxRetriesPerRequest: 3,
      lazyConnect: false,
    })
  }
  return redisInstance
}

/**
 * Disconnect the Redis client (useful for cleanup).
 */
export function disconnectRedis(): void {
  if (redisInstance) {
    redisInstance.disconnect()
    redisInstance = null
  }
}
