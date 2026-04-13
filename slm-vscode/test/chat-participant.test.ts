/**
 * Feature 23: VS Code Extension - Chat participant tests
 *
 * RED  - tests expect chat participant module with message formatting
 * GREEN - implement src/chat-participant.ts
 */
import { describe, it, expect } from "vitest"

describe("Feature 23 - VS Code Chat Participant", () => {
  it("exports formatChatPayload function", async () => {
    const { formatChatPayload } = await import("../src/chat-participant")
    expect(typeof formatChatPayload).toBe("function")
  })

  it("formatChatPayload creates correct structure", async () => {
    const { formatChatPayload } = await import("../src/chat-participant")
    const payload = formatChatPayload("How do I create a PDA?")
    expect(payload).toHaveProperty("messages")
    expect(payload).toHaveProperty("stream")
    expect(payload.stream).toBe(true)
    expect(payload.messages).toHaveLength(1)
    expect(payload.messages[0].role).toBe("user")
    expect(payload.messages[0].content).toBe("How do I create a PDA?")
  })

  it("formatChatPayload includes history when provided", async () => {
    const { formatChatPayload } = await import("../src/chat-participant")
    const history = [
      { role: "user" as const, content: "Hello" },
      { role: "assistant" as const, content: "Hi there!" },
    ]
    const payload = formatChatPayload("Follow up", history)
    expect(payload.messages).toHaveLength(3)
    expect(payload.messages[0].content).toBe("Hello")
    expect(payload.messages[2].content).toBe("Follow up")
  })

  it("exports parseSseChunk function", async () => {
    const { parseSseChunk } = await import("../src/chat-participant")
    expect(typeof parseSseChunk).toBe("function")
  })

  it("parseSseChunk extracts content from SSE data", async () => {
    const { parseSseChunk } = await import("../src/chat-participant")
    const line = 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
    expect(parseSseChunk(line)).toBe("Hello")
  })

  it("parseSseChunk returns null for [DONE]", async () => {
    const { parseSseChunk } = await import("../src/chat-participant")
    expect(parseSseChunk("data: [DONE]")).toBeNull()
  })

  it("parseSseChunk returns null for non-data lines", async () => {
    const { parseSseChunk } = await import("../src/chat-participant")
    expect(parseSseChunk(": keep-alive")).toBeNull()
    expect(parseSseChunk("")).toBeNull()
  })

  it("exports PARTICIPANT_ID constant", async () => {
    const { PARTICIPANT_ID } = await import("../src/chat-participant")
    expect(PARTICIPANT_ID).toBe("slm.chat")
  })
})
