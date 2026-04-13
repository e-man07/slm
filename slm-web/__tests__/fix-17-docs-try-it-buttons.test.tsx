/**
 * Fix 17: Docs try-it-out buttons
 * Add "Try it" buttons in docs page that navigate to /chat?prompt=<encoded>
 * Update chat page to read prompt search param and auto-send
 *
 * RED  - tests expect "Try it" buttons in docs, chat page reads prompt param
 * GREEN - add buttons to docs, update chat page
 */
import { describe, it, expect } from "vitest"
import { readFileSync } from "fs"
import { resolve } from "path"

describe("Fix 17 - Docs try-it-out buttons", () => {
  it("docs page contains 'Try it' buttons/links", () => {
    const docsPath = resolve(__dirname, "../app/docs/page.tsx")
    const content = readFileSync(docsPath, "utf-8")
    expect(content).toContain("Try it")
  })

  it("docs page links to /chat?prompt= with encoded prompts", () => {
    const docsPath = resolve(__dirname, "../app/docs/page.tsx")
    const content = readFileSync(docsPath, "utf-8")
    expect(content).toContain("/chat?prompt=")
  })

  it("chat page reads the prompt search param", () => {
    const chatPath = resolve(__dirname, "../app/chat/page.tsx")
    const content = readFileSync(chatPath, "utf-8")
    // Should use useSearchParams or searchParams to read prompt
    expect(content).toMatch(/searchParams|useSearchParams/)
    expect(content).toContain("prompt")
  })

  it("chat page calls sendMessage when prompt param is present", () => {
    const chatPath = resolve(__dirname, "../app/chat/page.tsx")
    const content = readFileSync(chatPath, "utf-8")
    // Should auto-send: read prompt, then call sendMessage
    expect(content).toContain("sendMessage")
    // Should handle decoding the prompt
    expect(content).toMatch(/decodeURIComponent|searchParams.*get.*prompt/)
  })
})
