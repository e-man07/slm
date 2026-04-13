import { describe, it, expect } from "vitest";
import { lookupError, isValidErrorCode } from "../../src/lib/errors.js";

describe("lookupError", () => {
  it("finds an Anchor framework error by decimal code", () => {
    const result = lookupError("2003");
    expect(result).not.toBeNull();
    expect(result!.program_name).toBe("Anchor Framework");
    expect(result!.error_name).toBe("ConstraintSeeds");
    expect(result!.code).toBe(2003);
    expect(result!.hex).toBe("0x7D3");
  });

  it("finds an error by hex code", () => {
    const result = lookupError("0x64");
    expect(result).not.toBeNull();
    expect(result!.error_name).toBe("InstructionMissing");
    expect(result!.code).toBe(100);
  });

  it("finds an error by uppercase hex code", () => {
    const result = lookupError("0X7D0");
    expect(result).not.toBeNull();
    expect(result!.error_name).toBe("ConstraintMut");
  });

  it("returns null for unknown error code below 6000", () => {
    const result = lookupError("5999");
    expect(result).toBeNull();
  });

  it("returns custom error fallback for unknown code >= 6000", () => {
    // Use a very high code that won't be in the table
    const result = lookupError("99999");
    expect(result).not.toBeNull();
    expect(result!.error_name).toBe("CustomError[93999]");
    expect(result!.code).toBe(99999);
  });

  it("returns null for NaN input", () => {
    const result = lookupError("not-a-number");
    expect(result).toBeNull();
  });

  it("filters by program_id when provided", () => {
    const result = lookupError("2003", "anchor_internal");
    expect(result).not.toBeNull();
    expect(result!.program_name).toBe("Anchor Framework");
  });

  it("returns null when filtering by non-matching program_id", () => {
    const result = lookupError("2003", "nonexistent_program");
    expect(result).toBeNull();
  });

  it("finds known program errors in 6000+ range from table", () => {
    // 6005 is NotEnoughPercent in the SPL Stake Pool program
    const result = lookupError("6005");
    expect(result).not.toBeNull();
    expect(result!.code).toBe(6005);
    // Should find the actual table entry, not the custom fallback
    expect(result!.error_name).not.toContain("CustomError");
  });

  it("returns custom fallback for unknown 6000+ codes", () => {
    // Use a code that is unlikely to be in the table
    const result = lookupError("7999");
    expect(result).not.toBeNull();
    expect(result!.error_name).toBe("CustomError[1999]");
    expect(result!.code).toBe(7999);
    expect(result!.hex).toBe("0x1f3f");
  });

  it("handles custom errors with program_id context", () => {
    const result = lookupError("6000", "ABC12345someprogram");
    expect(result).not.toBeNull();
    expect(result!.program_name).toContain("ABC12345");
    expect(result!.error_name).toBe("CustomError[0]");
  });

  it("trims whitespace from input", () => {
    const result = lookupError("  2003  ");
    expect(result).not.toBeNull();
    expect(result!.error_name).toBe("ConstraintSeeds");
  });
});

describe("isValidErrorCode", () => {
  it("returns true for valid decimal", () => {
    expect(isValidErrorCode("100")).toBe(true);
  });

  it("returns true for valid hex", () => {
    expect(isValidErrorCode("0x64")).toBe(true);
  });

  it("returns false for non-numeric input", () => {
    expect(isValidErrorCode("abc")).toBe(false);
  });

  it("returns false for negative numbers", () => {
    expect(isValidErrorCode("-1")).toBe(false);
  });

  it("returns true for zero", () => {
    expect(isValidErrorCode("0")).toBe(true);
  });
});
