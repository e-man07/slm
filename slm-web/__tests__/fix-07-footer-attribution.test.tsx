/**
 * Fix 7: Footer - Solana Foundation attribution
 * Add "Powered by Solana Foundation" or similar text in components/footer.tsx
 *
 * RED  - test expects "Solana Foundation" in footer, but it's not there
 * GREEN - add the attribution text
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { Footer } from "@/components/footer"

// Mock Next.js Link
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string
    children: React.ReactNode
    className?: string
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}))

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}))

describe("Fix 7 - Footer Solana Foundation attribution", () => {
  it("renders Solana Foundation attribution text", () => {
    render(<Footer />)
    expect(screen.getByText(/solana foundation/i)).toBeInTheDocument()
  })
})
