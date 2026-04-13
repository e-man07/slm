/**
 * Feature 23: VS Code Extension - Settings tests
 *
 * RED  - tests expect settings module with parsing/reading
 * GREEN - implement src/settings.ts
 */
import { describe, it, expect } from "vitest"

describe("Feature 23 - VS Code Extension Settings", () => {
  it("exports getSettings function", async () => {
    const { getSettings } = await import("../src/settings")
    expect(typeof getSettings).toBe("function")
  })

  it("returns settings with expected shape", async () => {
    const { getSettings } = await import("../src/settings")
    const settings = getSettings()
    expect(settings).toHaveProperty("apiKey")
    expect(settings).toHaveProperty("apiUrl")
    expect(settings).toHaveProperty("mode")
  })

  it("reads apiKey from vscode config", async () => {
    const { getSettings } = await import("../src/settings")
    const settings = getSettings()
    expect(settings.apiKey).toBe("slm_test_key")
  })

  it("reads apiUrl from vscode config", async () => {
    const { getSettings } = await import("../src/settings")
    const settings = getSettings()
    expect(settings.apiUrl).toBe("https://slm.dev/api")
  })

  it("reads mode from vscode config", async () => {
    const { getSettings } = await import("../src/settings")
    const settings = getSettings()
    expect(settings.mode).toBe("quality")
  })

  it("exports buildHeaders function", async () => {
    const { buildHeaders } = await import("../src/settings")
    expect(typeof buildHeaders).toBe("function")
  })

  it("buildHeaders includes Authorization when apiKey is set", async () => {
    const { buildHeaders } = await import("../src/settings")
    const headers = buildHeaders("slm_test123")
    expect(headers["Authorization"]).toBe("Bearer slm_test123")
    expect(headers["Content-Type"]).toBe("application/json")
  })

  it("buildHeaders omits Authorization when apiKey is empty", async () => {
    const { buildHeaders } = await import("../src/settings")
    const headers = buildHeaders("")
    expect(headers["Authorization"]).toBeUndefined()
  })
})
