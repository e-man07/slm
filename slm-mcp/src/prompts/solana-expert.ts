import { z } from "zod";
import type { GetPromptResult } from "@modelcontextprotocol/sdk/types.js";
import { SYSTEM_PROMPT } from "../lib/constants.js";

export const solanaExpertArgsSchema = {
  topic: z.string().describe("The Solana development topic to get help with"),
};

export async function getSolanaExpertPrompt(args: {
  topic: string;
}): Promise<GetPromptResult> {
  return {
    messages: [
      {
        role: "user",
        content: {
          type: "text",
          text: `${SYSTEM_PROMPT}\n\nPlease help me with the following Solana development topic: ${args.topic}`,
        },
      },
      {
        role: "assistant",
        content: {
          type: "text",
          text: `I'm SLM, your Solana and Anchor development expert. I'll help you with ${args.topic}. Let me provide accurate, secure, and up-to-date guidance using modern Anchor 0.30+ patterns.`,
        },
      },
      {
        role: "user",
        content: {
          type: "text",
          text: `Great, let's dive into ${args.topic}. Please provide detailed examples and explanations.`,
        },
      },
    ],
  };
}
