import { describe, it, expect } from "vitest";
import { handleDecodeError } from "../../src/tools/decode-error.js";

describe("handleDecodeError", () => {
  it("returns formatted result for a known error code", async () => {
    const result = await handleDecodeError({ error_code: "2003" });

    expect(result.content).toHaveLength(1);
    expect(result.content[0].type).toBe("text");
    const text = result.content[0].text;
    expect(text).toContain("ConstraintSeeds");
    expect(text).toContain("Anchor Framework");
    expect(text).toContain("2003");
  });

  it("returns formatted result for hex error code", async () => {
    const result = await handleDecodeError({ error_code: "0x64" });

    const text = result.content[0].text;
    expect(text).toContain("InstructionMissing");
    expect(text).toContain("100");
  });

  it("returns not-found message for unknown code below 6000", async () => {
    const result = await handleDecodeError({ error_code: "5999" });

    const text = result.content[0].text;
    expect(text).toContain("not found");
  });

  it("returns custom error info for 6000+ codes", async () => {
    const result = await handleDecodeError({ error_code: "7999" });

    const text = result.content[0].text;
    expect(text).toContain("CustomError");
    expect(text).toContain("7999");
  });

  it("filters by program_id when provided", async () => {
    const result = await handleDecodeError({
      error_code: "2003",
      program_id: "anchor_internal",
    });

    const text = result.content[0].text;
    expect(text).toContain("Anchor Framework");
    expect(text).toContain("ConstraintSeeds");
  });

  it("handles invalid input gracefully", async () => {
    const result = await handleDecodeError({ error_code: "not-a-number" });

    const text = result.content[0].text;
    expect(text).toContain("not found");
  });
});
