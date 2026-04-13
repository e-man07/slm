import { describe, it, expect } from "vitest";
import { readErrorsResource } from "../../src/resources/errors.js";

describe("readErrorsResource", () => {
  it("returns resource content with text type", async () => {
    const result = await readErrorsResource();

    expect(result.contents).toHaveLength(1);
    expect(result.contents[0].uri).toBe("solana://errors");
    expect(result.contents[0].mimeType).toBe("text/plain");
  });

  it("contains program and error count information", async () => {
    const result = await readErrorsResource();
    const text = result.contents[0].text as string;

    expect(text).toContain("Anchor Framework");
    expect(text).toContain("error");
  });

  it("contains multiple programs", async () => {
    const result = await readErrorsResource();
    const text = result.contents[0].text as string;

    // Should mention multiple programs
    expect(text).toContain("Program");
  });
});
