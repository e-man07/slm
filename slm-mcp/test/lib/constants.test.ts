import { describe, it, expect } from "vitest";
import {
  SYSTEM_PROMPT,
  DEPRECATED_PATTERNS,
  API_BASE_URL,
} from "../../src/lib/constants.js";

describe("SYSTEM_PROMPT", () => {
  it("is a non-empty string", () => {
    expect(typeof SYSTEM_PROMPT).toBe("string");
    expect(SYSTEM_PROMPT.length).toBeGreaterThan(100);
  });

  it("contains key guardrail rules", () => {
    expect(SYSTEM_PROMPT).toContain("Sealevel");
    expect(SYSTEM_PROMPT).toContain("Solana");
    expect(SYSTEM_PROMPT).toContain("Anchor");
    expect(SYSTEM_PROMPT).toContain("reentrancy");
    expect(SYSTEM_PROMPT).toContain("coral-xyz/anchor");
    expect(SYSTEM_PROMPT).toContain("declare_id!");
    expect(SYSTEM_PROMPT).toContain("load_instruction_at");
  });
});

describe("DEPRECATED_PATTERNS", () => {
  it("has exactly 6 patterns", () => {
    expect(DEPRECATED_PATTERNS).toHaveLength(6);
  });

  it("each pattern has regex, name, and suggestion", () => {
    for (const pattern of DEPRECATED_PATTERNS) {
      expect(pattern).toHaveProperty("regex");
      expect(pattern).toHaveProperty("name");
      expect(pattern).toHaveProperty("suggestion");
      expect(pattern.regex).toBeInstanceOf(RegExp);
      expect(typeof pattern.name).toBe("string");
      expect(typeof pattern.suggestion).toBe("string");
    }
  });

  it("matches declare_id!", () => {
    const p = DEPRECATED_PATTERNS.find((p) => p.name.includes("declare_id"));
    expect(p).toBeDefined();
    expect(p!.regex.test('declare_id!("Fg6Pa")')).toBe(true);
  });

  it("matches coral-xyz/anchor", () => {
    const p = DEPRECATED_PATTERNS.find((p) => p.name.includes("coral-xyz"));
    expect(p).toBeDefined();
    expect(p!.regex.test("coral-xyz/anchor")).toBe(true);
  });

  it("matches load_instruction_at", () => {
    const p = DEPRECATED_PATTERNS.find((p) =>
      p.name.includes("load_instruction_at"),
    );
    expect(p).toBeDefined();
    expect(p!.regex.test("load_instruction_at(0)")).toBe(true);
  });
});

describe("API_BASE_URL", () => {
  it("defaults to https://slm.dev/api", () => {
    expect(API_BASE_URL).toBe("https://slm.dev/api");
  });
});
