#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

// Tools
import { chatInputSchema, handleChat } from "./tools/chat.js";
import {
  decodeErrorInputSchema,
  handleDecodeError,
} from "./tools/decode-error.js";
import {
  explainTxInputSchema,
  handleExplainTx,
} from "./tools/explain-tx.js";
import {
  migrateCodeInputSchema,
  handleMigrateCode,
} from "./tools/migrate-code.js";
import {
  reviewCodeInputSchema,
  handleReviewCode,
} from "./tools/review-code.js";

// Resources
import { readErrorsResource } from "./resources/errors.js";
import { readEvalResultsResource } from "./resources/eval-results.js";
import { readSystemPromptResource } from "./resources/system-prompt.js";

// Prompts
import {
  solanaExpertArgsSchema,
  getSolanaExpertPrompt,
} from "./prompts/solana-expert.js";
import {
  migrationArgsSchema,
  getMigrationPrompt,
} from "./prompts/migration.js";
import {
  securityArgsSchema,
  getSecurityPrompt,
} from "./prompts/security.js";

export function createServer(): McpServer {
  const server = new McpServer(
    {
      name: "slm-mcp",
      version: "0.1.0",
    },
    {
      capabilities: {
        tools: {},
        resources: {},
        prompts: {},
      },
    },
  );

  // ── Tools ──────────────────────────────────────────────

  server.registerTool("slm_chat", {
    title: "SLM Chat",
    description:
      "Ask SLM (Solana Language Model) a question about Solana or Anchor development",
    inputSchema: chatInputSchema,
  }, async (args) => {
    return handleChat(args);
  });

  server.registerTool("slm_decode_error", {
    title: "Decode Solana Error",
    description:
      "Look up a Solana/Anchor error code and get the error name, message, and program",
    inputSchema: decodeErrorInputSchema,
  }, async (args) => {
    return handleDecodeError(args);
  });

  server.registerTool("slm_explain_tx", {
    title: "Explain Transaction",
    description:
      "Explain a Solana transaction by its signature — shows what happened and why",
    inputSchema: explainTxInputSchema,
  }, async (args) => {
    return handleExplainTx(args);
  });

  server.registerTool("slm_migrate_code", {
    title: "Migrate Anchor Code",
    description:
      "Migrate old Solana/Anchor code to modern Anchor 0.30+ patterns",
    inputSchema: migrateCodeInputSchema,
  }, async (args) => {
    return handleMigrateCode(args);
  });

  server.registerTool("slm_review_code", {
    title: "Review Solana Code",
    description:
      "Review Solana/Anchor code for deprecated patterns and common mistakes",
    inputSchema: reviewCodeInputSchema,
  }, async (args) => {
    return handleReviewCode(args);
  });

  // ── Resources ──────────────────────────────────────────

  server.registerResource("error-table", "solana://errors", {
    title: "Solana Error Table",
    description: "Complete table of Solana and Anchor error codes with messages",
    mimeType: "text/plain",
  }, async () => {
    return readErrorsResource();
  });

  server.registerResource("eval-results", "solana://eval-results", {
    title: "SLM Eval Results",
    description: "SLM model evaluation results (87.5% overall score)",
    mimeType: "text/plain",
  }, async () => {
    return readEvalResultsResource();
  });

  server.registerResource("system-prompt", "solana://system-prompt", {
    title: "SLM System Prompt",
    description: "The system prompt and guardrail rules used by SLM",
    mimeType: "text/plain",
  }, async () => {
    return readSystemPromptResource();
  });

  // ── Prompts ────────────────────────────────────────────

  server.registerPrompt("solana-expert", {
    title: "Solana Expert",
    description: "Get expert Solana development assistance on a specific topic",
    argsSchema: solanaExpertArgsSchema,
  }, async (args) => {
    return getSolanaExpertPrompt(args);
  });

  server.registerPrompt("anchor-migration", {
    title: "Anchor Migration",
    description:
      "Migrate old Anchor code to modern Anchor 0.30+ patterns",
    argsSchema: migrationArgsSchema,
  }, async (args) => {
    return getMigrationPrompt(args);
  });

  server.registerPrompt("security-review", {
    title: "Security Review",
    description:
      "Perform a security audit of Anchor code for common vulnerabilities",
    argsSchema: securityArgsSchema,
  }, async (args) => {
    return getSecurityPrompt(args);
  });

  return server;
}

// Only start the transport when run directly (not imported for tests)
const isDirectRun =
  process.argv[1] &&
  (process.argv[1].endsWith("index.js") ||
    process.argv[1].endsWith("index.ts"));

if (isDirectRun) {
  const server = createServer();
  const transport = new StdioServerTransport();
  server.connect(transport).then(() => {
    console.error("SLM MCP server running on stdio");
  });
}
