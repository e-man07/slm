import type { ReadResourceResult } from "@modelcontextprotocol/sdk/types.js";
import { SYSTEM_PROMPT } from "../lib/constants.js";

export async function readSystemPromptResource(): Promise<ReadResourceResult> {
  return {
    contents: [
      {
        uri: "solana://system-prompt",
        mimeType: "text/plain",
        text: SYSTEM_PROMPT,
      },
    ],
  };
}
