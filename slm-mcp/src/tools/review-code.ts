import { z } from "zod";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { DEPRECATED_PATTERNS } from "../lib/constants.js";

export const reviewCodeInputSchema = {
  code: z.string().max(64000).describe("Solana/Anchor code to review for deprecated patterns"),
};

interface ReviewCodeInput {
  code: string;
}

interface Issue {
  pattern: string;
  suggestion: string;
}

export async function handleReviewCode(input: ReviewCodeInput): Promise<CallToolResult> {
  const issues: Issue[] = [];

  for (const pattern of DEPRECATED_PATTERNS) {
    if (pattern.regex.test(input.code)) {
      issues.push({
        pattern: pattern.name,
        suggestion: pattern.suggestion,
      });
    }
  }

  if (issues.length === 0) {
    return {
      content: [
        {
          type: "text",
          text: "No deprecated patterns found. The code follows modern Solana/Anchor conventions.",
        },
      ],
    };
  }

  const lines = [
    `## Code Review: ${issues.length} issue${issues.length > 1 ? "s" : ""} found`,
    "",
  ];

  for (let i = 0; i < issues.length; i++) {
    lines.push(`### ${i + 1}. ${issues[i].pattern}`);
    lines.push("");
    lines.push(issues[i].suggestion);
    lines.push("");
  }

  return {
    content: [{ type: "text", text: lines.join("\n") }],
  };
}
