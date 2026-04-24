/**
 * Feature 21: Dashboard usage stats
 *
 * RED  - tests expect usage API route, usage logging, and dashboard stats rendering
 * GREEN - implement usage route, update middleware to log, update dashboard
 */
import { describe, it, expect } from "vitest"

describe("Feature 21 - Usage Stats", () => {
  describe("lib/db.ts usage functions", () => {
    it("exports logUsage function", async () => {
      const db = await import("@/lib/db")
      expect(typeof db.logUsage).toBe("function")
    })

    it("exports getUsageStats function", async () => {
      const db = await import("@/lib/db")
      expect(typeof db.getUsageStats).toBe("function")
    })

    it("exports getTodayTokensByUserId function", async () => {
      const db = await import("@/lib/db")
      expect(typeof db.getTodayTokensByUserId).toBe("function")
    })
  })

  describe("app/api/usage/route.ts", () => {
    it("exports GET handler", async () => {
      const usage = await import("@/app/api/usage/route")
      expect(typeof usage.GET).toBe("function")
    })

    it("returns 401 when no auth header", async () => {
      const usage = await import("@/app/api/usage/route")
      const request = new Request("http://localhost/api/usage")
      const response = await usage.GET(request)
      expect(response.status).toBe(401)
    })
  })

  describe("components/dashboard/usage-chart.tsx", () => {
    it("exports UsageChart component", async () => {
      const mod = await import("@/components/dashboard/usage-chart")
      expect(mod.UsageChart).toBeDefined()
    })
  })

  describe("components/dashboard/usage-stats.tsx", () => {
    it("exports UsageStats component", async () => {
      const mod = await import("@/components/dashboard/usage-stats")
      expect(mod.UsageStats).toBeDefined()
    })
  })
})
