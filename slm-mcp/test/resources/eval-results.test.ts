import { describe, it, expect } from "vitest";
import { readEvalResultsResource } from "../../src/resources/eval-results.js";

describe("readEvalResultsResource", () => {
  it("returns resource content with text type", async () => {
    const result = await readEvalResultsResource();

    expect(result.contents).toHaveLength(1);
    expect(result.contents[0].uri).toBe("solana://eval-results");
    expect(result.contents[0].mimeType).toBe("text/plain");
  });

  it("contains overall score information", async () => {
    const result = await readEvalResultsResource();
    const text = result.contents[0].text as string;

    expect(text).toContain("87.5%");
    expect(text).toContain("70");
    expect(text).toContain("80");
  });

  it("contains category breakdowns", async () => {
    const result = await readEvalResultsResource();
    const text = result.contents[0].text as string;

    expect(text).toContain("pda_derivation");
    expect(text).toContain("cpi_patterns");
    expect(text).toContain("error_handling");
  });
});
