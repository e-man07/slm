import { z } from "zod";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { callChat } from "../lib/api-client.js";

export const chatInputSchema = {
  message: z.string().max(32000).describe("Message to send to Sealevel"),
  context: z
    .string()
    .max(32000)
    .optional()
    .describe("Optional context (e.g. surrounding code, error logs)"),
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
