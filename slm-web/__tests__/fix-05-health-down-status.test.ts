/**
 * Fix 5: Health endpoint "down" status
 * Return "down" instead of "degraded" when sglang fetch throws
 *
 * RED  - test expects status="down" on fetch failure, but source returns "degraded"
 * GREEN - change the source
 */
import { describe, it, expect, vi, beforeEach } from "vitest"

// We need to mock the fetch global and the constants module
vi.mock("@/lib/constants", () => ({
  API_URLS: {
    SGLANG_BASE: "http://localhost:30000",
    HEALTH: "/health",
    HELIUS_BASE: "https://api.helius.xyz",
    CHAT: "/v1/chat/completions",
  },
}))

describe("Fix 5 - Health endpoint down status", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("returns status 'down' when sglang fetch throws", async () => {
    // Simulate connection refused
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Connection refused")),
    )

    const { GET } = await import("@/app/api/health/route")
    const response = await GET()
    const body = await response.json()

    expect(body.status).toBe("down")
    expect(body.sglang).toBe(false)
  })

  it("returns status 'ok' when sglang is healthy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true }),
    )

    // Re-import to get fresh module
    vi.resetModules()
    const { GET } = await import("@/app/api/health/route")
    const response = await GET()
    const body = await response.json()

    expect(body.status).toBe("ok")
    expect(body.sglang).toBe(true)
  })
})
