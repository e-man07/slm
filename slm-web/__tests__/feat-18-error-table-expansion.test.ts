/**
 * Feature 18: Error table expansion (61 -> 200+ errors, 2 -> 10+ programs)
 *
 * RED  - tests verify the expanded error-table.json has correct structure
 *        and sufficient coverage of programs and errors
 * GREEN - run build-error-table.ts script to generate expanded table
 */
import { describe, it, expect } from "vitest"
import errorTable from "@/data/error-table.json"

describe("Feature 18 - Error table expansion", () => {
  it("has valid JSON structure with programs array", () => {
    expect(errorTable).toHaveProperty("programs")
    expect(Array.isArray(errorTable.programs)).toBe(true)
  })

  it("each program has required fields", () => {
    for (const program of errorTable.programs) {
      expect(program).toHaveProperty("program_id")
      expect(program).toHaveProperty("program_name")
      expect(program).toHaveProperty("errors")
      expect(typeof program.program_id).toBe("string")
      expect(typeof program.program_name).toBe("string")
      expect(Array.isArray(program.errors)).toBe(true)
      expect(program.errors.length).toBeGreaterThan(0)
    }
  })

  it("each error entry has code, hex, name, and message", () => {
    for (const program of errorTable.programs) {
      for (const error of program.errors) {
        expect(error).toHaveProperty("code")
        expect(error).toHaveProperty("hex")
        expect(error).toHaveProperty("name")
        expect(error).toHaveProperty("message")
        expect(typeof error.code).toBe("number")
        expect(typeof error.hex).toBe("string")
        expect(typeof error.name).toBe("string")
        expect(typeof error.message).toBe("string")
        expect(error.hex).toMatch(/^0x[0-9A-Fa-f]+$/)
      }
    }
  })

  it("has at least 10 programs", () => {
    expect(errorTable.programs.length).toBeGreaterThanOrEqual(10)
  })

  it("has at least 200 total errors", () => {
    const totalErrors = errorTable.programs.reduce(
      (sum, p) => sum + p.errors.length,
      0,
    )
    expect(totalErrors).toBeGreaterThanOrEqual(200)
  })

  it("includes Anchor Framework errors", () => {
    const anchor = errorTable.programs.find(
      (p) => p.program_name === "Anchor Framework",
    )
    expect(anchor).toBeDefined()
    expect(anchor!.errors.length).toBeGreaterThanOrEqual(30)
  })

  it("includes SPL Token errors", () => {
    const splToken = errorTable.programs.find(
      (p) => p.program_id === "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    )
    expect(splToken).toBeDefined()
    expect(splToken!.errors.length).toBeGreaterThanOrEqual(14)
  })

  it("includes SPL Token-2022 errors", () => {
    const token2022 = errorTable.programs.find(
      (p) => p.program_id === "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    )
    expect(token2022).toBeDefined()
    expect(token2022!.errors.length).toBeGreaterThanOrEqual(10)
  })

  it("includes System Program errors", () => {
    const system = errorTable.programs.find(
      (p) => p.program_id === "11111111111111111111111111111111",
    )
    expect(system).toBeDefined()
    expect(system!.errors.length).toBeGreaterThanOrEqual(5)
  })

  it("includes DeFi program errors (Jupiter, Orca, or Raydium)", () => {
    const defiNames = ["Jupiter", "Orca", "Raydium"]
    const defiPrograms = errorTable.programs.filter((p) =>
      defiNames.some((name) =>
        p.program_name.toLowerCase().includes(name.toLowerCase()),
      ),
    )
    expect(defiPrograms.length).toBeGreaterThanOrEqual(2)
  })

  it("has no duplicate error codes within a single program", () => {
    for (const program of errorTable.programs) {
      const codes = program.errors.map((e) => e.code)
      const uniqueCodes = new Set(codes)
      expect(uniqueCodes.size).toBe(codes.length)
    }
  })

  it("hex values match their decimal codes", () => {
    for (const program of errorTable.programs) {
      for (const error of program.errors) {
        // Compare case-insensitively since hex format varies
        const parsed = parseInt(error.hex, 16)
        expect(parsed).toBe(error.code)
      }
    }
  })
})
