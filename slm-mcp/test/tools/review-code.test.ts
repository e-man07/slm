import { describe, it, expect } from "vitest";
import { handleReviewCode } from "../../src/tools/review-code.js";

describe("handleReviewCode", () => {
  it("detects declare_id! usage", async () => {
    const result = await handleReviewCode({
      code: 'declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFi43Z");',
    });

    const text = result.content[0].text;
    expect(text).toContain("declare_id!");
    expect(text).toContain("declare_program!");
  });

  it("detects coral-xyz/anchor usage", async () => {
    const result = await handleReviewCode({
      code: 'use anchor_lang from "coral-xyz/anchor";',
    });

    const text = result.content[0].text;
    expect(text).toContain("coral-xyz/anchor");
    expect(text).toContain("solana-foundation/anchor");
  });

  it("detects load_instruction_at usage", async () => {
    const result = await handleReviewCode({
      code: "let ix = load_instruction_at(0, &ix_sysvar)?;",
    });

    const text = result.content[0].text;
    expect(text).toContain("load_instruction_at");
    expect(text).toContain("get_instruction_relative");
  });

  it("detects reentrancy guard pattern", async () => {
    const result = await handleReviewCode({
      code: "// Add a reentrancy_guard to prevent attacks",
    });

    const text = result.content[0].text;
    expect(text).toContain("reentrancy");
    expect(text).toContain("not needed");
  });

  it("detects closed account discriminator pattern", async () => {
    const result = await handleReviewCode({
      code: "// Check for closed_account_discriminator",
    });

    const text = result.content[0].text;
    expect(text).toContain("closed account discriminator");
  });

  it("detects float non-determinism pattern", async () => {
    const result = await handleReviewCode({
      code: "// Beware of float non-determinism in calculations",
    });

    const text = result.content[0].text;
    expect(text).toContain("float");
    expect(text).toContain("deterministic");
  });

  it("detects multiple issues in one code block", async () => {
    const code = `
declare_id!("Fg6Pa");
use anchor_lang from "coral-xyz/anchor";
let ix = load_instruction_at(0, &ix_sysvar)?;
`;
    const result = await handleReviewCode({ code });

    const text = result.content[0].text;
    expect(text).toContain("declare_id!");
    expect(text).toContain("coral-xyz/anchor");
    expect(text).toContain("load_instruction_at");
    // Should show count of issues
    expect(text).toContain("3");
  });

  it("returns clean report for code without issues", async () => {
    const result = await handleReviewCode({
      code: `
use anchor_lang::prelude::*;

declare_program!(my_program);

#[program]
pub mod my_program {
    use super::*;
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        Ok(())
    }
}
`,
    });

    const text = result.content[0].text;
    expect(text).toContain("No deprecated patterns");
  });
});
