import type { ReadResourceResult } from "@modelcontextprotocol/sdk/types.js";
import { errorTable } from "../lib/errors.js";

interface ProgramEntry {
  program_id: string;
  program_name: string;
  errors: Array<{ code: number; hex: string; name: string; message: string }>;
}

export async function readErrorsResource(): Promise<ReadResourceResult> {
  const programs = (errorTable as { programs: ProgramEntry[] }).programs;
  const lines = [
    "# Solana/Anchor Error Table",
    "",
  ];

  for (const program of programs) {
    lines.push(`## Program: ${program.program_name} (${program.program_id})`);
    lines.push(`${program.errors.length} errors defined`);
    lines.push("");

    for (const error of program.errors) {
      lines.push(`- **${error.name}** (${error.code} / ${error.hex}): ${error.message}`);
    }
    lines.push("");
  }

  return {
    contents: [
      {
        uri: "solana://errors",
        mimeType: "text/plain",
        text: lines.join("\n"),
      },
    ],
  };
}
