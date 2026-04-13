import { z } from "zod";
import type { GetPromptResult } from "@modelcontextprotocol/sdk/types.js";
import { SYSTEM_PROMPT } from "../lib/constants.js";

export const migrationArgsSchema = {
  code: z.string().describe("The Solana/Anchor code to migrate to modern patterns"),
};

export async function getMigrationPrompt(args: {
  code: string;
}): Promise<GetPromptResult> {
  return {
    messages: [
      {
        role: "user",
        content: {
          type: "text",
          text: `${SYSTEM_PROMPT}\n\nPlease migrate the following code to modern Anchor 0.30+ patterns. Specifically update:\n- declare_id! to declare_program!\n- coral-xyz/anchor to solana-foundation/anchor\n- Manual space calculation to InitSpace derive macro\n- bumps.get("name") to ctx.bumps.field_name\n- load_instruction_at to get_instruction_relative\n\nCode to migrate:\n\`\`\`\n${args.code}\n\`\`\``,
        },
      },
      {
        role: "assistant",
        content: {
          type: "text",
          text: "I'll migrate this code to modern Anchor 0.30+ patterns. Let me analyze the code and apply all necessary updates.",
        },
      },
    ],
  };
}
