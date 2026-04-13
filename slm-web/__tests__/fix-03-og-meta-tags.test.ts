/**
 * Fix 3: OG/social meta tags
 * Add openGraph + twitter metadata in app/layout.tsx
 *
 * RED  - test expects metadata.openGraph and metadata.twitter to be defined
 * GREEN - add the metadata
 */
import { describe, it, expect, vi } from "vitest"

// Mock next/font/google to avoid font loading in tests
vi.mock("next/font/google", () => ({
  Geist: () => ({ variable: "--font-sans" }),
  JetBrains_Mono: () => ({ variable: "--font-mono" }),
}))

vi.mock("@/components/theme-provider", () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
}))

vi.mock("@/components/ui/sonner", () => ({
  Toaster: () => null,
}))

vi.mock("@/lib/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}))

describe("Fix 3 - OG/social meta tags", () => {
  it("exports metadata with openGraph fields", async () => {
    const layoutModule = await import("@/app/layout")
    const metadata = (layoutModule as Record<string, unknown>).metadata as {
      openGraph?: {
        title?: string
        description?: string
        siteName?: string
        type?: string
      }
    }
    expect(metadata.openGraph).toBeDefined()
    expect(metadata.openGraph!.title).toBeDefined()
    expect(metadata.openGraph!.description).toBeDefined()
    expect(metadata.openGraph!.siteName).toBe("SLM")
  })

  it("exports metadata with twitter card fields", async () => {
    const layoutModule = await import("@/app/layout")
    const metadata = (layoutModule as Record<string, unknown>).metadata as {
      twitter?: {
        card?: string
        title?: string
        description?: string
      }
    }
    expect(metadata.twitter).toBeDefined()
    expect(metadata.twitter!.card).toBe("summary_large_image")
  })
})
