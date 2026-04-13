/**
 * Fix 11: Full markdown rendering in chat
 * Replace regex-based code block parser with react-markdown + remark-gfm
 *
 * RED  - tests expect proper markdown rendering (bold, italic, lists, headers, links, code blocks)
 * GREEN - replace parseCodeBlocks with ReactMarkdown
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

function makeMsg(content: string, overrides?: Partial<ChatMessageType>): ChatMessageType {
  return {
    id: "test-1",
    role: "assistant",
    content,
    timestamp: Date.now(),
    isStreaming: false,
    ...overrides,
  }
}

describe("Fix 11 - Markdown rendering in chat", () => {
  it("renders **bold** text as <strong>", () => {
    render(<ChatMessage message={makeMsg("This is **bold** text")} />)
    const strong = document.querySelector("strong")
    expect(strong).not.toBeNull()
    expect(strong!.textContent).toBe("bold")
  })

  it("renders *italic* text as <em>", () => {
    render(<ChatMessage message={makeMsg("This is *italic* text")} />)
    const em = document.querySelector("em")
    expect(em).not.toBeNull()
    expect(em!.textContent).toBe("italic")
  })

  it("renders unordered lists as <ul> with <li> items", () => {
    const content = "Items:\n\n- First\n- Second\n- Third"
    render(<ChatMessage message={makeMsg(content)} />)
    const items = document.querySelectorAll("li")
    expect(items.length).toBeGreaterThanOrEqual(3)
    expect(items[0].textContent).toContain("First")
  })

  it("renders ordered lists as <ol> with <li> items", () => {
    const content = "Steps:\n\n1. First\n2. Second\n3. Third"
    render(<ChatMessage message={makeMsg(content)} />)
    const ol = document.querySelector("ol")
    expect(ol).not.toBeNull()
    const items = ol!.querySelectorAll("li")
    expect(items.length).toBeGreaterThanOrEqual(3)
  })

  it("renders headings (## Header) as heading elements", () => {
    const content = "## My Header\n\nSome text"
    render(<ChatMessage message={makeMsg(content)} />)
    const heading = document.querySelector("h2")
    expect(heading).not.toBeNull()
    expect(heading!.textContent).toBe("My Header")
  })

  it("renders links as <a> tags", () => {
    const content = "Visit [Solana](https://solana.com) for more"
    render(<ChatMessage message={makeMsg(content)} />)
    const link = document.querySelector("a")
    expect(link).not.toBeNull()
    expect(link!.getAttribute("href")).toBe("https://solana.com")
    expect(link!.textContent).toBe("Solana")
  })

  it("renders inline code with <code> elements", () => {
    const content = "Use `anchor build` to compile"
    render(<ChatMessage message={makeMsg(content)} />)
    const code = document.querySelector("code")
    expect(code).not.toBeNull()
    expect(code!.textContent).toBe("anchor build")
  })

  it("renders fenced code blocks with CodeBlockClient (language label + copy button)", () => {
    const content = "Here is code:\n\n```rust\nfn main() {}\n```"
    render(<ChatMessage message={makeMsg(content)} />)
    // CodeBlockClient should render with the language label
    expect(screen.getByText("Rust")).toBeInTheDocument()
    // Code content should be present
    expect(screen.getByText("fn main() {}")).toBeInTheDocument()
  })

  it("still shows streaming cursor for streaming messages", () => {
    render(
      <ChatMessage
        message={makeMsg("Partial content", { isStreaming: true })}
      />,
    )
    // The streaming cursor should be an animated pulse element
    const cursor = document.querySelector(".animate-pulse")
    expect(cursor).not.toBeNull()
  })
})
