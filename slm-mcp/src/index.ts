#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createServer as createHttpServer } from "http";

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
    title: "Sealevel Chat",
    description:
      "Ask Sealevel (Solana Language Model) a question about Solana or Anchor development",
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
    title: "Sealevel Eval Results",
    description: "Sealevel model evaluation results (87.5% overall score)",
    mimeType: "text/plain",
  }, async () => {
    return readEvalResultsResource();
  });

  server.registerResource("system-prompt", "solana://system-prompt", {
    title: "Sealevel System Prompt",
    description: "The system prompt and guardrail rules used by Sealevel",
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
  const mode = process.env.MCP_TRANSPORT ?? (process.env.PORT ? "http" : "stdio");

  if (mode === "http") {
    // HTTP transport — for remote deployment (GCP, Akash, etc.)
    const port = parseInt(process.env.PORT ?? "8080", 10);
    const server = createServer();

    const httpServer = createHttpServer(async (req, res) => {
      // CORS
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE");
      res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, mcp-session-id");
      res.setHeader("Access-Control-Expose-Headers", "mcp-session-id");

      if (req.method === "OPTIONS") {
        res.writeHead(204);
        res.end();
        return;
      }

      // Health check
      if (req.method === "GET" && req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", server: "slm-mcp", version: "0.1.0" }));
        return;
      }

      // MCP endpoint
      if (req.url === "/mcp" || req.url === "/") {
        const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
        res.on("close", () => { transport.close(); });
        await server.connect(transport);
        await transport.handleRequest(req, res);
        return;
      }

      res.writeHead(404);
      res.end("Not found");
    });

    httpServer.listen(port, () => {
      console.error(`Sealevel MCP server running on http://0.0.0.0:${port}/mcp`);
    });
  } else {
    // stdio transport — for local use
    const server = createServer();
    const transport = new StdioServerTransport();
    server.connect(transport).then(() => {
      console.error("Sealevel MCP server running on stdio");
    });
  }
}
