import { z } from "zod";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { callExplainTx } from "../lib/api-client.js";

export const explainTxInputSchema = {
  signature: z
    .string()
    .describe("Solana transaction signature (base58 string, typically 87-88 characters). Example: '5U3..abc'. Found in explorer URLs, wallet history, or program logs"),
};

interface ExplainTxInput {
  signature: string;
}

export async function handleExplainTx(
  input: ExplainTxInput,
): Promise<CallToolResult> {
  try {
    const { txData, explanation } = await callExplainTx(input.signature);

    const lines = [
      `## Transaction: ${input.signature}`,
      "",
    ];

    if (txData && typeof txData === "object") {
      lines.push("### Transaction Data");
      lines.push("```json");
      lines.push(JSON.stringify(txData, null, 2));
      lines.push("```");
      lines.push("");
    }

    lines.push("### Explanation");
    lines.push(explanation);

    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown error occurred";
    return {
      content: [{ type: "text", text: `Error explaining transaction: ${message}` }],
      isError: true,
    };
  }
}
