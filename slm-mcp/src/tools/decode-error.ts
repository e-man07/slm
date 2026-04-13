import { z } from "zod";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { lookupError } from "../lib/errors.js";

export const decodeErrorInputSchema = {
  error_code: z.string().describe("Error code in decimal (e.g. 2003) or hex (e.g. 0x7D3)"),
  program_id: z.string().optional().describe("Optional program ID to narrow the search"),
};

interface DecodeErrorInput {
  error_code: string;
  program_id?: string;
}

export async function handleDecodeError(input: DecodeErrorInput): Promise<CallToolResult> {
  const result = lookupError(input.error_code, input.program_id);

  if (!result) {
    return {
      content: [
        {
          type: "text",
          text: `Error code ${input.error_code} not found in the Solana/Anchor error table.${
            input.program_id
              ? ` (filtered by program: ${input.program_id})`
              : ""
          }\n\nTip: If this is a custom program error (>= 6000), provide the program_id to get more context.`,
        },
      ],
    };
  }

  const lines = [
    `## Error Lookup: ${result.error_name}`,
    "",
    `| Field | Value |`,
    `|-------|-------|`,
    `| Program | ${result.program_name} |`,
    `| Error | ${result.error_name} |`,
    `| Code | ${result.code} (${result.hex}) |`,
    `| Message | ${result.error_message} |`,
  ];

  return {
    content: [{ type: "text", text: lines.join("\n") }],
  };
}
