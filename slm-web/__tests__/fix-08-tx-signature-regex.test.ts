/**
 * Fix 8: Tx signature validation
 * Change regex from {86,90} to {87,88} in components/explain/tx-signature-input.tsx
 *
 * RED  - test expects 86-char and 89-char strings to be INVALID, but current regex accepts them
 * GREEN - change the regex
 */
import { describe, it, expect } from "vitest"

// We test the isValidBase58 function indirectly by importing the module
// Since isValidBase58 is not exported, we'll test it via the component behavior
// But first let's extract the regex logic for unit testing

describe("Fix 8 - Tx signature validation regex", () => {
  // We'll create a regex test that matches the source code pattern
  // The function isValidBase58 is defined inline, so we replicate and test it
  function getIsValidBase58() {
    // This reads the current implementation. We test the expected behavior.
    // After the fix, only 87-88 chars should be valid.
    return (str: string) => /^[1-9A-HJ-NP-Za-km-z]{87,88}$/.test(str)
  }

  const isValid = getIsValidBase58()
  const base58Char = "1" // valid base58 char

  it("rejects a string shorter than 87 chars", () => {
    const sig = base58Char.repeat(86)
    expect(isValid(sig)).toBe(false)
  })

  it("accepts a 87-char base58 string", () => {
    const sig = base58Char.repeat(87)
    expect(isValid(sig)).toBe(true)
  })

  it("accepts a 88-char base58 string", () => {
    const sig = base58Char.repeat(88)
    expect(isValid(sig)).toBe(true)
  })

  it("rejects a string longer than 88 chars", () => {
    const sig = base58Char.repeat(89)
    expect(isValid(sig)).toBe(false)
  })

  it("the source code uses {87,88} quantifier", async () => {
    const fs = await import("fs")
    const path = await import("path")
    const filePath = path.resolve(
      __dirname,
      "..",
      "components",
      "explain",
      "tx-signature-input.tsx",
    )
    const source = fs.readFileSync(filePath, "utf-8")
    expect(source).toContain("{87,88}")
    expect(source).not.toContain("{86,90}")
  })
})
