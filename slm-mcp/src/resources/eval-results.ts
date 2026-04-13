import { createRequire } from "node:module";
import type { ReadResourceResult } from "@modelcontextprotocol/sdk/types.js";

const require = createRequire(import.meta.url);
const evalResults: EvalResults = require("../../data/eval-results.json");

interface CategoryResult {
  passed: number;
  total: number;
  score: number;
}

interface EvalResults {
  timestamp: string;
  model_path: string;
  overall: { passed: number; total: number; score: number };
  categories: Record<string, CategoryResult>;
}

export async function readEvalResultsResource(): Promise<ReadResourceResult> {
  const overall = evalResults.overall;
  const scorePercent = (overall.score * 100).toFixed(1);

  const lines = [
    "# SLM Evaluation Results",
    "",
    `**Overall Score: ${scorePercent}%** (${overall.passed}/${overall.total} passed)`,
    "",
    `Model: ${evalResults.model_path}`,
    `Evaluated: ${evalResults.timestamp}`,
    "",
    "## Category Breakdown",
    "",
    "| Category | Score | Passed | Total |",
    "|----------|-------|--------|-------|",
  ];

  for (const [name, cat] of Object.entries(evalResults.categories)) {
    const pct = (cat.score * 100).toFixed(1);
    lines.push(`| ${name} | ${pct}% | ${cat.passed} | ${cat.total} |`);
  }

  return {
    contents: [
      {
        uri: "solana://eval-results",
        mimeType: "text/plain",
        text: lines.join("\n"),
      },
    ],
  };
}
