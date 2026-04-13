import { describe, it, expect } from "vitest";
import { getSecurityPrompt } from "../../src/prompts/security.js";

describe("getSecurityPrompt", () => {
  it("returns messages with correct structure", async () => {
    const result = await getSecurityPrompt({ code: "fn transfer() {}" });

    expect(result.messages).toBeDefined();
    expect(result.messages.length).toBeGreaterThanOrEqual(2);
  });

  it("includes the code in the user message", async () => {
    const code = "pub fn withdraw(ctx: Context<Withdraw>) -> Result<()> { Ok(()) }";
    const result = await getSecurityPrompt({ code });

    const userMsg = result.messages.find((m) => m.role === "user");
    expect(userMsg).toBeDefined();
    expect(userMsg!.content.text).toContain(code);
  });

  it("includes security review instructions", async () => {
    const result = await getSecurityPrompt({ code: "some code" });

    const hasSecurityContext = result.messages.some(
      (m) =>
        m.content.text.includes("security") || m.content.text.includes("vulnerabilit"),
    );
    expect(hasSecurityContext).toBe(true);
  });
});
