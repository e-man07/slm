/**
 * Fix 10: VS Code tab in install section
 * Add a 4th tab for VS Code extension install in the landing page app/page.tsx
 *
 * RED  - test expects a "VS Code" tab trigger text, but it doesn't exist
 * GREEN - add the tab
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

// Re-use the same mocks as fix-02
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
  }: {
    href: string
    children: React.ReactNode
  }) => <a href={href}>{children}</a>,
}))

vi.mock("@hugeicons/react", () => ({
  HugeiconsIcon: () => null,
}))

vi.mock("@hugeicons/core-free-icons", () => ({
  BubbleChatIcon: "BubbleChatIcon",
  InspectCodeIcon: "InspectCodeIcon",
  Alert01Icon: "Alert01Icon",
  ApiIcon: "ApiIcon",
}))

vi.mock("@/components/shared/page-layout", () => ({
  PageLayout: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}))

vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    ...props
  }: {
    children: React.ReactNode
    asChild?: boolean
    size?: string
    variant?: string
  }) => {
    if (props.asChild) return <>{children}</>
    return <button>{children}</button>
  },
}))

vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CardContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CardHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CardTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}))

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}))

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TabsContent: ({
    children,
    value,
  }: {
    children: React.ReactNode
    value: string
  }) => <div data-value={value}>{children}</div>,
  TabsList: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TabsTrigger: ({
    children,
  }: {
    children: React.ReactNode
    value?: string
  }) => <div>{children}</div>,
}))

vi.mock("@/components/eval/eval-category-chart", () => ({
  EvalCategoryChart: () => null,
}))

vi.mock("@/data/eval-results.json", () => ({
  default: {
    overall: { score: 0.875, passed: 70, total: 80 },
    categories: {},
  },
}))

describe("Fix 10 - VS Code tab in install section", () => {
  it("renders a VS Code tab trigger", async () => {
    const { default: Page } = await import("@/app/page")
    render(<Page />)
    const matches = screen.getAllByText(/VS Code/i)
    expect(matches.length).toBeGreaterThanOrEqual(1)
    // The first match should be the tab trigger (exact text)
    expect(matches[0].textContent).toBe("VS Code")
  })

  it("renders VS Code extension install content", async () => {
    const { default: Page } = await import("@/app/page")
    render(<Page />)
    // Should contain ext install command
    expect(screen.getByText(/ext install slm/i)).toBeInTheDocument()
  })
})
