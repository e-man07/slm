/**
 * Fix 4: Tx result - show block/timestamp
 * Add blockTime display in components/explain/tx-result.tsx
 *
 * RED  - test expects blockTime to be rendered, but it is not in the current source
 * GREEN - add blockTime rendering
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { TxResult } from "@/components/explain/tx-result"
import type { TxData } from "@/lib/sse"

// Mock child components
vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
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

vi.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}))

vi.mock("@/components/chat/streaming-text", () => ({
  StreamingText: ({ text }: { text: string }) => <span>{text}</span>,
}))

vi.mock("@/lib/helius", () => ({
  shortenAddress: (addr: string) => addr.slice(0, 6),
  formatSolAmount: (v: number) => String(v),
}))

const TX_DATA: TxData = {
  status: "success",
  type: "TRANSFER",
  fee: 0.000005,
  feePayer: "7nYBm5mkVF1fGDFv2JYsbRpDeKXNv1D1CYmB1GhLNsuP",
  blockTime: 1712345678,
  instructions: [{}],
  tokenTransfers: [],
}

describe("Fix 4 - Tx result block time display", () => {
  it("renders blockTime as a human-readable date", () => {
    render(<TxResult txData={TX_DATA} explanation="" isStreaming={false} />)
    // blockTime 1712345678 => April 5, 2024 (unix timestamp)
    // We expect some date string to be rendered
    const dateEl = screen.getByText(/2024/)
    expect(dateEl).toBeInTheDocument()
  })

  it("renders the 'Block Time' label", () => {
    render(<TxResult txData={TX_DATA} explanation="" isStreaming={false} />)
    expect(screen.getByText("Block Time")).toBeInTheDocument()
  })
})
