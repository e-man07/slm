/**
 * Fix 2: Landing CTA
 * Change second button href from /docs to /dashboard in app/page.tsx
 *
 * RED  - test expects href="/dashboard", but source currently uses "/docs"
 * GREEN - change the source
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

// Mock Next.js Link to render an anchor tag
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
  }: {
    href: string
    children: React.ReactNode
  }) => <a href={href}>{children}</a>,
}))

// Mock all heavy imports used by the page
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
    // When asChild is true, the child Link should render; otherwise wrap in button
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
  TabsContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TabsList: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TabsTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
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

describe("Fix 2 - Landing CTA button", () => {
  it("renders the second hero button with href='/dashboard'", async () => {
    const { default: Page } = await import("@/app/page")
    render(<Page />)
    const link = screen.getByRole("link", { name: /api docs/i })
    expect(link).toHaveAttribute("href", "/dashboard")
  })
})
