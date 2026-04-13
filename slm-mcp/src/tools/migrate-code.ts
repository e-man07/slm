import { z } from "zod";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { callChat } from "../lib/api-client.js";

export const migrateCodeInputSchema = {
  code: z
    .string()
    .describe("Solana/Anchor code to migrate to modern patterns"),
};

interface MigrateCodeInput {
  code: string;
}

export async function handleMigrateCode(
  input: MigrateCodeInput,
): Promise<CallToolResult> {
  const migrationPrompt = `Please migrate the following Solana/Anchor code to modern Anchor 0.30+ patterns. Specifically:
- Replace declare_id! with declare_program!
- Replace coral-xyz/anchor references with solana-foundation/anchor
- Use InitSpace derive macro instead of manual space calculation
- Use ctx.bumps.field_name instead of bumps.get("field_name")
- Remove unnecessary reentrancy guards
- Replace load_instruction_at with get_instruction_relative

Here is the code to migrate:

\`\`\`
${input.code}
\`\`\``;

  try {
    const text = await callChat(migrationPrompt);
    return {
      content: [{ type: "text", text }],
    };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown error occurred";
    return {
      content: [{ type: "text", text: `Error migrating code: ${message}` }],
      isError: true,
    };
  }
}
