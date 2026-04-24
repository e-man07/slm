import { describe, it, expect } from "vitest";
import { readSystemPromptResource } from "../../src/resources/system-prompt.js";

describe("readSystemPromptResource", () => {
  it("returns resource content with text type", async () => {
    const result = await readSystemPromptResource();

    expect(result.contents).toHaveLength(1);
    expect(result.contents[0].uri).toBe("solana://system-prompt");
    expect(result.contents[0].mimeType).toBe("text/plain");
  });

  it("contains the Sealevel system prompt text", async () => {
    const result = await readSystemPromptResource();
    const text = result.contents[0].text as string;

    expect(text).toContain("Sealevel");
    expect(text).toContain("Solana");
    expect(text).toContain("Anchor");
    expect(text).toContain("reentrancy");
  });

  it("contains all 6 guardrail rules", async () => {
    const result = await readSystemPromptResource();
    const text = result.contents[0].text as string;

    // The guardrail rules
    expect(text).toContain("coral-xyz");
    expect(text).toContain("declare_id!");
    expect(text).toContain("reentrancy");
    expect(text).toContain("discriminator");
    expect(text).toContain("Floats");
    expect(text).toContain("load_instruction_at");
  });
});
