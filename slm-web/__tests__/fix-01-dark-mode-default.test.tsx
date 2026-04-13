/**
 * Fix 1: Dark mode default
 * Change defaultTheme from "system" to "dark" in components/theme-provider.tsx
 *
 * RED  - test expects defaultTheme="dark", but source currently uses "system"
 * GREEN - change the source
 */
import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"
import { ThemeProvider } from "@/components/theme-provider"

// Mock next-themes so we can inspect the props passed to NextThemesProvider
const capturedProps: Record<string, unknown>[] = []

vi.mock("next-themes", () => ({
  ThemeProvider: (props: Record<string, unknown>) => {
    capturedProps.push(props)
    return props.children
  },
  useTheme: () => ({ resolvedTheme: "dark", setTheme: () => {} }),
}))

describe("Fix 1 - Dark mode default", () => {
  it("passes defaultTheme='dark' to NextThemesProvider", () => {
    capturedProps.length = 0
    render(
      <ThemeProvider>
        <div />
      </ThemeProvider>,
    )
    const props = capturedProps[0]
    expect(props).toBeDefined()
    expect(props.defaultTheme).toBe("dark")
  })
})
