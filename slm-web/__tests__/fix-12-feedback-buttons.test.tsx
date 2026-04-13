/**
 * Fix 12: Feedback buttons (thumbs up/down) on chat messages
 *
 * RED  - tests expect feedback buttons on assistant messages, feedback field on ChatMessage type
 * GREEN - add feedback field + thumbs up/down buttons
 */
import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
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

function makeAssistantMsg(
  content: string,
  overrides?: Partial<ChatMessageType>,
): ChatMessageType {
  return {
    id: "asst-1",
    role: "assistant",
    content,
    timestamp: Date.now(),
    isStreaming: false,
    ...overrides,
  }
}

function makeUserMsg(content: string): ChatMessageType {
  return {
    id: "user-1",
    role: "user",
    content,
    timestamp: Date.now(),
  }
}

describe("Fix 12 - Feedback buttons", () => {
  it("shows thumbs up and thumbs down buttons on completed assistant messages", () => {
    render(<ChatMessage message={makeAssistantMsg("Hello from SLM")} />)
    expect(screen.getByLabelText("Thumbs up")).toBeInTheDocument()
    expect(screen.getByLabelText("Thumbs down")).toBeInTheDocument()
  })

  it("does NOT show feedback buttons on user messages", () => {
    render(<ChatMessage message={makeUserMsg("Hello")} />)
    expect(screen.queryByLabelText("Thumbs up")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Thumbs down")).not.toBeInTheDocument()
  })

  it("does NOT show feedback buttons on streaming assistant messages", () => {
    render(
      <ChatMessage
        message={makeAssistantMsg("Thinking...", { isStreaming: true })}
      />,
    )
    expect(screen.queryByLabelText("Thumbs up")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Thumbs down")).not.toBeInTheDocument()
  })

  it("highlights thumbs up when clicked", () => {
    render(<ChatMessage message={makeAssistantMsg("Good answer")} />)
    const upBtn = screen.getByLabelText("Thumbs up")
    fireEvent.click(upBtn)
    // After clicking thumbs up, it should be visually active (data-active attribute)
    expect(upBtn.getAttribute("data-active")).toBe("true")
  })

  it("highlights thumbs down when clicked", () => {
    render(<ChatMessage message={makeAssistantMsg("Bad answer")} />)
    const downBtn = screen.getByLabelText("Thumbs down")
    fireEvent.click(downBtn)
    expect(downBtn.getAttribute("data-active")).toBe("true")
  })

  it("toggles off when clicking the same button again", () => {
    render(<ChatMessage message={makeAssistantMsg("Toggle test")} />)
    const upBtn = screen.getByLabelText("Thumbs up")
    fireEvent.click(upBtn)
    expect(upBtn.getAttribute("data-active")).toBe("true")
    fireEvent.click(upBtn)
    expect(upBtn.getAttribute("data-active")).not.toBe("true")
  })

  it("ChatMessage type supports optional feedback field", () => {
    // Verify the type accepts the feedback field without TypeScript errors
    const msg: ChatMessageType = {
      id: "test-1",
      role: "assistant",
      content: "Test",
      timestamp: Date.now(),
      feedback: "up",
    }
    expect(msg.feedback).toBe("up")
  })
})
