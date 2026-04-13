import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const errorTable: ErrorTable = require("../../data/error-table.json");

interface ErrorEntry {
  code: number;
  hex: string;
  name: string;
  message: string;
}

interface ProgramEntry {
  program_id: string;
  program_name: string;
  errors: ErrorEntry[];
}

interface ErrorTable {
  programs: ProgramEntry[];
}

export interface ErrorLookupResult {
  program_name: string;
  error_name: string;
  error_message: string;
  code: number;
  hex: string;
}

function parseErrorCode(input: string): number {
  const trimmed = input.trim();
  if (trimmed.startsWith("0x") || trimmed.startsWith("0X")) {
    return parseInt(trimmed, 16);
  }
  return parseInt(trimmed, 10);
}

export function lookupError(
  errorCode: string,
  programId?: string,
): ErrorLookupResult | null {
  const code = parseErrorCode(errorCode);
  if (isNaN(code)) return null;

  const programs = programId
    ? errorTable.programs.filter((p) => p.program_id === programId)
    : errorTable.programs;

  for (const program of programs) {
    const error = program.errors.find((e) => e.code === code);
    if (error) {
      return {
        program_name: program.program_name,
        error_name: error.name,
        error_message: error.message,
        code: error.code,
        hex: error.hex,
      };
    }
  }

  // For custom program errors (6000+), provide context
  if (code >= 6000) {
    const variantIndex = code - 6000;
    return {
      program_name: programId
        ? `Program ${programId.slice(0, 8)}...`
        : "Unknown Program",
      error_name: `CustomError[${variantIndex}]`,
      error_message: `Custom program error at index ${variantIndex} (code ${code} / 0x${code.toString(16)}). Check the program's error enum for the specific variant.`,
      code,
      hex: `0x${code.toString(16)}`,
    };
  }

  return null;
}

export function isValidErrorCode(input: string): boolean {
  const code = parseErrorCode(input);
  return !isNaN(code) && code >= 0;
}

export { errorTable };
