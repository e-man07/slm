/**
 * Fix 15: Typing indicator (3 dots before first token)
 * Show animated 3-dot indicator when isStreaming && !content
 *
 * RED  - test expects a typing indicator with 3 dots
 * GREEN - add the TypingIndicator component
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { ChatMessage } from "@/components/chat/chat-message"
import type { ChatMessage as ChatMessageType } from "@/hooks/use-chat"

// Mock child components
vi.mock("@/components/shared/copy-button", () => ({
  CopyButton: ({ value }: { value: string }) => (
    <button aria-label="Copy to clipboard">{value.slice(0, 10)}</button>
  ),
}))

vi.mock("@/components/chat/streaming-text", () => ({
  StreamingText: ({ text }: { text: string }) => <span data-testid="streaming">{text}</span>,
}))

function makeMsg(
  content: string,
  overrides?: Partial<ChatMessageType>,
): ChatMessageType {
  return {
    id: "test-1",
    role: "assistant",
    content,
    timestamp: Date.now(),
    isStreaming: false,
    ...overrides,
  }
}

describe("Fix 15 - Typing indicator", () => {
  it("shows typing indicator when streaming with no content", () => {
    render(
      <ChatMessage
        message={makeMsg("", { isStreaming: true })}
      />,
    )
    const indicator = screen.getByTestId("typing-indicator")
    expect(indicator).toBeInTheDocument()
  })

  it("typing indicator has exactly 3 dots", () => {
    render(
      <ChatMessage
        message={makeMsg("", { isStreaming: true })}
      />,
    )
    const dots = screen.getByTestId("typing-indicator").querySelectorAll("span")
    expect(dots.length).toBe(3)
  })

  it("does NOT show typing indicator when content exists", () => {
    render(
      <ChatMessage
        message={makeMsg("Hello", { isStreaming: true })}
      />,
    )
    expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument()
  })

  it("does NOT show typing indicator on completed messages", () => {
    render(
      <ChatMessage
        message={makeMsg("", { isStreaming: false })}
      />,
    )
    expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument()
  })
})
