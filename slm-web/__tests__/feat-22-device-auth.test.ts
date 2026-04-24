/**
 * Tests for device auth flow — POST /api/auth/device, GET /api/auth/device/poll, POST /api/auth/device/verify
 */
import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock Redis
const mockRedisGet = vi.fn()
const mockRedisSet = vi.fn()
const mockRedisDel = vi.fn()
vi.mock("@/lib/redis", () => ({
  getRedis: () => ({
    get: mockRedisGet,
    set: mockRedisSet,
    del: mockRedisDel,
  }),
}))

// Mock DB
const mockGetUserByApiKey = vi.fn()
const mockGenerateApiKeyForUser = vi.fn()
vi.mock("@/lib/db", () => ({
  getUserByApiKey: (...args: unknown[]) => mockGetUserByApiKey(...args),
  generateApiKeyForUser: (...args: unknown[]) => mockGenerateApiKeyForUser(...args),
}))

// Mock auth
vi.mock("@/lib/auth-next", () => ({
  auth: vi.fn().mockResolvedValue(null),
}))

vi.mock("@/lib/middleware", () => ({
  resolveUserId: vi.fn().mockResolvedValue(null),
}))

import { POST as devicePost } from "@/app/api/auth/device/route"
import { GET as devicePoll } from "@/app/api/auth/device/poll/route"
import { POST as deviceVerify } from "@/app/api/auth/device/verify/route"

beforeEach(() => {
  vi.clearAllMocks()
})

// ---- POST /api/auth/device — Create device code ----

describe("POST /api/auth/device", () => {
  it("returns a device code and verification URL", async () => {
    mockRedisSet.mockResolvedValue("OK")

    const req = new Request("http://localhost/api/auth/device", { method: "POST" })
    const res = await devicePost(req)
    const data = await res.json()

    expect(res.status).toBe(200)
    expect(data.userCode).toBeDefined()
    expect(data.userCode).toMatch(/^[A-Z0-9]{4}-[A-Z0-9]{4}$/)
    expect(data.verificationUrl).toContain("/device")
    expect(data.expiresIn).toBe(600)
    expect(data.interval).toBe(5)
  })

  it("stores device code in Redis with TTL", async () => {
    mockRedisSet.mockResolvedValue("OK")

    const req = new Request("http://localhost/api/auth/device", { method: "POST" })
    await devicePost(req)

    expect(mockRedisSet).toHaveBeenCalledTimes(1)
    const [key, value, ex, ttl] = mockRedisSet.mock.calls[0]
    expect(key).toMatch(/^device:/)
    expect(ex).toBe("EX")
    expect(ttl).toBe(600)
    const parsed = JSON.parse(value)
    expect(parsed.status).toBe("pending")
    expect(parsed.userId).toBeNull()
    expect(parsed.apiKey).toBeNull()
  })
})

// ---- GET /api/auth/device/poll — Poll for completion ----

describe("GET /api/auth/device/poll", () => {
  it("returns pending when code exists but not verified", async () => {
    mockRedisGet.mockResolvedValue(JSON.stringify({
      status: "pending",
      userId: null,
      apiKey: null,
    }))

    const req = new Request("http://localhost/api/auth/device/poll?code=ABCD-1234")
    const res = await devicePoll(req)
    const data = await res.json()

    expect(res.status).toBe(200)
    expect(data.status).toBe("pending")
    expect(data.apiKey).toBeUndefined()
  })

  it("returns complete with API key when verified", async () => {
    mockRedisGet.mockResolvedValue(JSON.stringify({
      status: "complete",
      userId: 42,
      apiKey: "slm_abc123def456",
      userName: "kshitij",
      tier: "free",
    }))

    const req = new Request("http://localhost/api/auth/device/poll?code=ABCD-1234")
    const res = await devicePoll(req)
    const data = await res.json()

    expect(res.status).toBe(200)
    expect(data.status).toBe("complete")
    expect(data.apiKey).toBe("slm_abc123def456")
    expect(data.user.name).toBe("kshitij")
    expect(data.user.tier).toBe("free")
  })

  it("returns 404 for expired/invalid code", async () => {
    mockRedisGet.mockResolvedValue(null)

    const req = new Request("http://localhost/api/auth/device/poll?code=XXXX-9999")
    const res = await devicePoll(req)

    expect(res.status).toBe(404)
  })

  it("returns 400 when no code param", async () => {
    const req = new Request("http://localhost/api/auth/device/poll")
    const res = await devicePoll(req)

    expect(res.status).toBe(400)
  })

  it("deletes code from Redis after successful poll", async () => {
    mockRedisGet.mockResolvedValue(JSON.stringify({
      status: "complete",
      userId: 42,
      apiKey: "slm_abc123def456",
      userName: "kshitij",
      tier: "free",
    }))
    mockRedisDel.mockResolvedValue(1)

    const req = new Request("http://localhost/api/auth/device/poll?code=ABCD-1234")
    await devicePoll(req)

    expect(mockRedisDel).toHaveBeenCalledWith("device:ABCD-1234")
  })
})

// ---- POST /api/auth/device/verify — Browser verifies code ----

describe("POST /api/auth/device/verify", () => {
  it("returns 401 when not authenticated", async () => {
    const { resolveUserId } = await import("@/lib/middleware")
    vi.mocked(resolveUserId).mockResolvedValue(null)

    const req = new Request("http://localhost/api/auth/device/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "ABCD-1234" }),
    })
    const res = await deviceVerify(req)

    expect(res.status).toBe(401)
  })

  it("returns 404 for expired/invalid code", async () => {
    const { resolveUserId } = await import("@/lib/middleware")
    vi.mocked(resolveUserId).mockResolvedValue(42)
    mockRedisGet.mockResolvedValue(null)

    const req = new Request("http://localhost/api/auth/device/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "XXXX-9999" }),
    })
    const res = await deviceVerify(req)

    expect(res.status).toBe(404)
  })

  it("returns 409 for already-used code", async () => {
    const { resolveUserId } = await import("@/lib/middleware")
    vi.mocked(resolveUserId).mockResolvedValue(42)
    mockRedisGet.mockResolvedValue(JSON.stringify({
      status: "complete",
      userId: 99,
      apiKey: "slm_old",
    }))

    const req = new Request("http://localhost/api/auth/device/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "ABCD-1234" }),
    })
    const res = await deviceVerify(req)

    expect(res.status).toBe(409)
  })

  it("verifies code and generates API key", async () => {
    const { resolveUserId } = await import("@/lib/middleware")
    vi.mocked(resolveUserId).mockResolvedValue(42)
    mockRedisGet.mockResolvedValue(JSON.stringify({
      status: "pending",
      userId: null,
      apiKey: null,
    }))
    mockGenerateApiKeyForUser.mockResolvedValue({
      id: 42,
      name: "kshitij",
      apiKey: "slm_newkey12345678",
      tier: "free",
    })
    mockRedisSet.mockResolvedValue("OK")

    const req = new Request("http://localhost/api/auth/device/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "ABCD-1234" }),
    })
    const res = await deviceVerify(req)
    const data = await res.json()

    expect(res.status).toBe(200)
    expect(data.success).toBe(true)

    // Should update Redis with completed status
    expect(mockRedisSet).toHaveBeenCalledTimes(1)
    const [key, value, _ex, _ttl] = mockRedisSet.mock.calls[0]
    expect(key).toBe("device:ABCD-1234")
    const parsed = JSON.parse(value)
    expect(parsed.status).toBe("complete")
    expect(parsed.userId).toBe(42)
    expect(parsed.apiKey).toBe("slm_newkey12345678")
    expect(parsed.userName).toBe("kshitij")
    expect(parsed.tier).toBe("free")
  })

  it("returns 400 when no code in body", async () => {
    const { resolveUserId } = await import("@/lib/middleware")
    vi.mocked(resolveUserId).mockResolvedValue(42)

    const req = new Request("http://localhost/api/auth/device/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    })
    const res = await deviceVerify(req)

    expect(res.status).toBe(400)
  })
})
