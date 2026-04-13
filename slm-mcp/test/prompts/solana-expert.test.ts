import { describe, it, expect } from "vitest";
import { getSolanaExpertPrompt } from "../../src/prompts/solana-expert.js";

describe("getSolanaExpertPrompt", () => {
  it("returns messages with system and user roles", async () => {
    const result = await getSolanaExpertPrompt({ topic: "PDAs" });

    expect(result.messages).toBeDefined();
    expect(result.messages.length).toBeGreaterThanOrEqual(2);

    const roles = result.messages.map((m) => m.role);
    expect(roles).toContain("user");
  });

  it("includes the topic in the user message", async () => {
    const result = await getSolanaExpertPrompt({ topic: "cross-program invocations" });

    const userMsg = result.messages.find((m) => m.role === "user");
    expect(userMsg).toBeDefined();
    expect(userMsg!.content.text).toContain("cross-program invocations");
  });

  it("includes SLM context in system message", async () => {
    const result = await getSolanaExpertPrompt({ topic: "tokens" });

    // Should have system-level context about being a Solana expert
    const hasSystemContext = result.messages.some(
      (m) => m.content.text.includes("Solana") || m.content.text.includes("SLM"),
    );
    expect(hasSystemContext).toBe(true);
  });
});
