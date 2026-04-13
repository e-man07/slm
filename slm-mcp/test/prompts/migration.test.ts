import { describe, it, expect } from "vitest";
import { getMigrationPrompt } from "../../src/prompts/migration.js";

describe("getMigrationPrompt", () => {
  it("returns messages with correct structure", async () => {
    const result = await getMigrationPrompt({ code: "declare_id!()" });

    expect(result.messages).toBeDefined();
    expect(result.messages.length).toBeGreaterThanOrEqual(2);
  });

  it("includes the code in the user message", async () => {
    const code = 'declare_id!("Fg6PaFpoGXkYsid");';
    const result = await getMigrationPrompt({ code });

    const userMsg = result.messages.find((m) => m.role === "user");
    expect(userMsg).toBeDefined();
    expect(userMsg!.content.text).toContain(code);
  });

  it("includes migration instructions", async () => {
    const result = await getMigrationPrompt({ code: "old code" });

    const hasInstructions = result.messages.some(
      (m) =>
        m.content.text.includes("migrate") || m.content.text.includes("Anchor 0.30"),
    );
    expect(hasInstructions).toBe(true);
  });
});
