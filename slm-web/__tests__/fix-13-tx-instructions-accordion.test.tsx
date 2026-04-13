/**
 * Fix 13: Tx result - collapsible instructions list
 * Add an Accordion in tx-result.tsx showing each instruction
 *
 * RED  - tests expect instruction details to be rendered in an accordion
 * GREEN - add Accordion with instruction details
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

// Mock Accordion to render everything (no collapse behavior in test)
vi.mock("@/components/ui/accordion", () => ({
  Accordion: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="accordion">{children}</div>
  ),
  AccordionItem: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="accordion-item">{children}</div>
  ),
  AccordionTrigger: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="accordion-trigger">{children}</div>
  ),
  AccordionContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="accordion-content">{children}</div>
  ),
}))

vi.mock("@/components/chat/streaming-text", () => ({
  StreamingText: ({ text }: { text: string }) => <span>{text}</span>,
}))

vi.mock("@/lib/helius", () => ({
  shortenAddress: (addr: string) => `${addr.slice(0, 4)}...${addr.slice(-4)}`,
  formatSolAmount: (v: number) => String(v),
}))

const TX_DATA_WITH_INSTRUCTIONS: TxData = {
  status: "success",
  type: "SWAP",
  fee: 0.000005,
  feePayer: "7nYBm5mkVF1fGDFv2JYsbRpDeKXNv1D1CYmB1GhLNsuP",
  blockTime: 1712345678,
  instructions: [
    {
      programId: "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
      accounts: ["acc1", "acc2", "acc3"],
      data: "3Bxs411Dtc7pkFQj0123456789",
    },
    {
      programId: "11111111111111111111111111111111",
      accounts: ["acc4"],
      data: "abcdef",
    },
  ],
  tokenTransfers: [],
}

describe("Fix 13 - Tx result collapsible instructions", () => {
  it("renders an 'Instructions' section heading", () => {
    render(
      <TxResult
        txData={TX_DATA_WITH_INSTRUCTIONS}
        explanation=""
        isStreaming={false}
      />,
    )
    // There may be multiple "Instructions" labels (grid label + accordion section)
    const elements = screen.getAllByText("Instructions")
    expect(elements.length).toBeGreaterThanOrEqual(1)
    // The accordion should be present
    expect(screen.getByTestId("accordion")).toBeInTheDocument()
  })

  it("shows shortened program ID for each instruction", () => {
    render(
      <TxResult
        txData={TX_DATA_WITH_INSTRUCTIONS}
        explanation=""
        isStreaming={false}
      />,
    )
    // First instruction: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA
    // shortenAddress => "Toke...Q5DA"
    expect(screen.getByText("Toke...Q5DA")).toBeInTheDocument()
    // Second instruction: 11111111111111111111111111111111
    // shortenAddress => "1111...1111"
    expect(screen.getByText("1111...1111")).toBeInTheDocument()
  })

  it("shows account count for each instruction", () => {
    render(
      <TxResult
        txData={TX_DATA_WITH_INSTRUCTIONS}
        explanation=""
        isStreaming={false}
      />,
    )
    // First instruction has 3 accounts
    expect(screen.getByText("3 accounts")).toBeInTheDocument()
    // Second instruction has 1 account
    expect(screen.getByText("1 account")).toBeInTheDocument()
  })

  it("shows data preview for each instruction in accordion content", () => {
    render(
      <TxResult
        txData={TX_DATA_WITH_INSTRUCTIONS}
        explanation=""
        isStreaming={false}
      />,
    )
    // Data preview should show the data string
    expect(screen.getByText(/3Bxs411Dtc7pkFQj0123456789/)).toBeInTheDocument()
  })

  it("does not render instructions section when there are no instructions", () => {
    const txData: TxData = {
      ...TX_DATA_WITH_INSTRUCTIONS,
      instructions: [],
    }
    render(
      <TxResult txData={txData} explanation="" isStreaming={false} />,
    )
    // The accordion should not be rendered
    expect(screen.queryByTestId("accordion")).not.toBeInTheDocument()
    // No account counts should be visible
    expect(screen.queryByText(/accounts/)).not.toBeInTheDocument()
  })
})
