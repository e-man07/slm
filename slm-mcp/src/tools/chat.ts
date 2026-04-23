import { z } from "zod";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { callChat } from "../lib/api-client.js";

export const chatInputSchema = {
  message: z.string().max(32000).describe("Your Solana/Anchor development question or request. Examples: 'How do I derive a PDA?', 'Write an escrow program in Anchor', 'Explain CPI calls'"),
  context: z
    .string()
    .max(32000)
    .optional()
    .describe("Optional surrounding code, error logs, or Cargo.toml contents to give the model more context for a better answer"),
};

interface ChatInput {
  message: string;
  context?: string;
}

export async function handleChat(input: ChatInput): Promise<CallToolResult> {
  try {
    const text = await callChat(input.message, input.context);
    return {
      content: [{ type: "text", text }],
    };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown error occurred";
    return {
      content: [{ type: "text", text: `Error: ${message}` }],
      isError: true,
    };
  }
}
