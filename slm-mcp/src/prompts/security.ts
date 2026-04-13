import { z } from "zod";
import type { GetPromptResult } from "@modelcontextprotocol/sdk/types.js";
import { SYSTEM_PROMPT } from "../lib/constants.js";

export const securityArgsSchema = {
  code: z.string().describe("The Anchor code to review for security vulnerabilities"),
};

export async function getSecurityPrompt(args: {
  code: string;
}): Promise<GetPromptResult> {
  return {
    messages: [
      {
        role: "user",
        content: {
          type: "text",
          text: `${SYSTEM_PROMPT}\n\nPlease perform a thorough security review of the following Anchor code. Check for common vulnerabilities including:\n- Missing signer checks\n- Missing owner checks\n- Integer overflow/underflow\n- Unchecked account validation\n- PDA seed collisions\n- Missing close constraints\n- Unsafe arithmetic\n\nCode to review:\n\`\`\`\n${args.code}\n\`\`\``,
        },
      },
      {
        role: "assistant",
        content: {
          type: "text",
          text: "I'll perform a comprehensive security audit of this Anchor code, checking for common vulnerabilities and potential attack vectors.",
        },
      },
    ],
  };
}
