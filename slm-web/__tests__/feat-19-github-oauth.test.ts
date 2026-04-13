/**
 * Feature 19: GitHub OAuth with NextAuth.js
 *
 * RED  - tests expect auth config, API key generation, and DB schema helpers
 * GREEN - implement lib/auth.ts, lib/db.ts, and the NextAuth route
 */
import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock next-auth since it depends on server runtime
vi.mock("next-auth", () => ({
  default: vi.fn((config: unknown) => ({
    handlers: { GET: vi.fn(), POST: vi.fn() },
    auth: vi.fn(),
    signIn: vi.fn(),
    signOut: vi.fn(),
  })),
}))

vi.mock("next-auth/providers/github", () => ({
  default: vi.fn((opts: Record<string, unknown>) => ({ id: "github", name: "GitHub", ...opts })),
}))

describe("Feature 19 - GitHub OAuth", () => {
  describe("lib/auth.ts exports", () => {
    it("exports authConfig with GitHub provider", async () => {
      const { authConfig } = await import("@/lib/auth")
      expect(authConfig).toBeDefined()
      expect(authConfig.providers).toBeDefined()
      expect(authConfig.providers.length).toBeGreaterThanOrEqual(1)
    })

    it("authConfig has session strategy set to jwt", async () => {
      const { authConfig } = await import("@/lib/auth")
      expect(authConfig.session?.strategy).toBe("jwt")
    })

    it("authConfig has callbacks defined", async () => {
      const { authConfig } = await import("@/lib/auth")
      expect(authConfig.callbacks).toBeDefined()
    })
  })

  describe("lib/db.ts exports", () => {
    it("exports query function", async () => {
      const db = await import("@/lib/db")
      expect(typeof db.query).toBe("function")
    })

    it("exports getOrCreateUser function", async () => {
      const db = await import("@/lib/db")
      expect(typeof db.getOrCreateUser).toBe("function")
    })

    it("exports getUserByApiKey function", async () => {
      const db = await import("@/lib/db")
      expect(typeof db.getUserByApiKey).toBe("function")
    })
  })

  describe("API key generation", () => {
    it("exports generateApiKey function", async () => {
      const { generateApiKey } = await import("@/lib/auth")
      expect(typeof generateApiKey).toBe("function")
    })

    it("generates keys with slm_ prefix", async () => {
      const { generateApiKey } = await import("@/lib/auth")
      const key = generateApiKey()
      expect(key).toMatch(/^slm_/)
    })

    it("generates unique keys on each call", async () => {
      const { generateApiKey } = await import("@/lib/auth")
      const key1 = generateApiKey()
      const key2 = generateApiKey()
      expect(key1).not.toBe(key2)
    })

    it("generates keys of sufficient length (at least 20 chars)", async () => {
      const { generateApiKey } = await import("@/lib/auth")
      const key = generateApiKey()
      expect(key.length).toBeGreaterThanOrEqual(20)
    })
  })

  describe("DB migration SQL", () => {
    it("exports MIGRATION_SQL constant", async () => {
      const { MIGRATION_SQL } = await import("@/lib/db")
      expect(typeof MIGRATION_SQL).toBe("string")
      expect(MIGRATION_SQL).toContain("CREATE TABLE")
      expect(MIGRATION_SQL).toContain("users")
      expect(MIGRATION_SQL).toContain("github_id")
      expect(MIGRATION_SQL).toContain("api_key")
      expect(MIGRATION_SQL).toContain("tier")
    })
  })
})
