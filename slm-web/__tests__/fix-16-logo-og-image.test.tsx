/**
 * Fix 16: Logo SVG + OG image
 * Create logo.svg, og-image.svg, update layout.tsx metadata, update nav-bar.tsx
 *
 * RED  - tests expect logo SVG in nav-bar, OG metadata in layout
 * GREEN - create assets and update components
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { readFileSync, existsSync } from "fs"
import { resolve } from "path"

// Test 1: logo.svg exists
describe("Fix 16 - Logo SVG + OG image", () => {
  it("public/logo.svg exists and is valid SVG", () => {
    const logoPath = resolve(__dirname, "../public/logo.svg")
    expect(existsSync(logoPath)).toBe(true)
    const content = readFileSync(logoPath, "utf-8")
    expect(content).toContain("<svg")
    expect(content).toContain("Sealevel")
  })

  it("public/og-image.svg exists and contains Sealevel branding", () => {
    const ogPath = resolve(__dirname, "../public/og-image.svg")
    expect(existsSync(ogPath)).toBe(true)
    const content = readFileSync(ogPath, "utf-8")
    expect(content).toContain("<svg")
    expect(content).toContain("Sealevel")
  })

  it("layout.tsx metadata references og-image", async () => {
    // Read the layout file and check metadata
    const layoutPath = resolve(__dirname, "../app/layout.tsx")
    const content = readFileSync(layoutPath, "utf-8")
    expect(content).toContain("og-image")
  })

  it("nav-bar.tsx uses the SVG logo instead of plain text", () => {
    const navPath = resolve(__dirname, "../components/nav-bar.tsx")
    const content = readFileSync(navPath, "utf-8")
    // Should reference logo.svg or use an <img> or Image component
    expect(content).toContain("logo.svg")
  })
})
