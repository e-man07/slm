/**
 * Fix 6: Docs - add upstream_timeout error code
 * Add a row for upstream_timeout (504) in the error codes table in app/docs/page.tsx
 *
 * RED  - test expects "upstream_timeout" text in the page, but it's not there
 * GREEN - add the table row
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

// Mock all UI components
vi.mock("@/components/shared/page-layout", () => ({
  PageLayout: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
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

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
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

vi.mock("@/components/ui/table", () => ({
  Table: ({ children }: { children: React.ReactNode }) => (
    <table>{children}</table>
  ),
  TableBody: ({ children }: { children: React.ReactNode }) => (
    <tbody>{children}</tbody>
  ),
  TableCell: ({ children }: { children: React.ReactNode }) => (
    <td>{children}</td>
  ),
  TableHead: ({ children }: { children: React.ReactNode }) => (
    <th>{children}</th>
  ),
  TableHeader: ({ children }: { children: React.ReactNode }) => (
    <thead>{children}</thead>
  ),
  TableRow: ({ children }: { children: React.ReactNode }) => (
    <tr>{children}</tr>
  ),
}))

vi.mock("@/components/shared/code-block", () => ({
  CodeBlock: () => <pre />,
}))

describe("Fix 6 - upstream_timeout error code in docs", () => {
  it("renders an upstream_timeout row in the error codes table", async () => {
    const { default: DocsPage } = await import("@/app/docs/page")
    render(<DocsPage />)
    expect(screen.getByText("upstream_timeout")).toBeInTheDocument()
  })

  it("shows 504 status code for upstream_timeout", async () => {
    const { default: DocsPage } = await import("@/app/docs/page")
    render(<DocsPage />)
    // Find the 504 text node
    expect(screen.getByText("504")).toBeInTheDocument()
  })
})
