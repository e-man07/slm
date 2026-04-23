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
import { readSystemPromptResource } from "./resources/system-prompt.js";

// Prompts
import {
  securityArgsSchema,
  getSecurityPrompt,
} from "./prompts/security.js";

// Request context for per-user auth
import { requestContext } from "./lib/request-context.js";

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
      "Ask Sealevel, a Solana-specialized 7B coding LLM, any question about Solana or Anchor development. Use this for: writing Anchor programs, explaining Solana concepts (PDAs, CPIs, SPL tokens, accounts), generating Rust code for on-chain programs, answering Solana architecture questions, and debugging Solana-specific issues. Trained on 270K Solana records from 500+ repos. Enforces modern Anchor 0.30+ patterns. Pass surrounding code as context for better answers.",
    inputSchema: chatInputSchema,
  }, async (args) => {
    return handleChat(args);
  });

  server.registerTool("slm_decode_error", {
    title: "Decode Solana Error",
    description:
      "Look up a Solana or Anchor program error code and get the error name, message, and originating program. Accepts decimal (e.g. 2003, 6000) or hex (e.g. 0x7D3, 0x1771) error codes. Covers 1,914 errors across 41 programs including SPL Token, System Program, Anchor framework errors, Metaplex, and more. Use this when you encounter a Solana transaction error, program error code, or need to understand what a specific error means and how to fix it.",
    inputSchema: decodeErrorInputSchema,
  }, async (args) => {
    return handleDecodeError(args);
  });

  server.registerTool("slm_explain_tx", {
    title: "Explain Transaction",
    description:
      "Explain a Solana transaction by its signature in human-readable terms. Fetches on-chain data (instructions, token transfers, SOL transfers, fee, accounts involved) and provides an AI-generated explanation of what the transaction did and why. Use this when you have a transaction signature and need to understand its purpose, debug a failed transaction, or analyze on-chain activity.",
    inputSchema: explainTxInputSchema,
  }, async (args) => {
    return handleExplainTx(args);
  });

  server.registerTool("slm_migrate_code", {
    title: "Migrate Anchor Code",
    description:
      "Migrate old Solana/Anchor code to modern Anchor 0.30+ patterns. Handles: declare_id! to declare_program!, coral-xyz to solana-foundation imports, ctx.bumps.get() to ctx.bumps.name, removing unnecessary lifetimes on #[account] structs, ProgramResult to Result<()>, and other deprecated patterns. Pass the full Rust source code (up to 64KB) and get back the migrated version.",
    inputSchema: migrateCodeInputSchema,
  }, async (args) => {
    return handleMigrateCode(args);
  });

  server.registerTool("slm_review_code", {
    title: "Review Solana Code",
    description:
      "Review Solana/Anchor Rust code for deprecated patterns, security issues, and common mistakes. Checks for: deprecated declare_id! macro, old coral-xyz/project-serum imports, missing signer/owner checks, unsafe arithmetic, PDA seed collisions, missing close constraints, reentrancy anti-patterns, and other Solana-specific issues. Returns a list of findings with line references and suggested fixes. Pass up to 64KB of Rust code.",
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

  server.registerResource("system-prompt", "solana://system-prompt", {
    title: "Sealevel System Prompt",
    description: "The system prompt and guardrail rules used by Sealevel",
    mimeType: "text/plain",
  }, async () => {
    return readSystemPromptResource();
  });

  // ── Prompts ────────────────────────────────────────────

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

    const ALLOWED_ORIGINS = new Set([
      "https://sealevel.tech",
      "https://www.sealevel.tech",
      "https://api.sealevel.tech",
      process.env.CORS_ORIGIN,
    ].filter(Boolean));

    const httpServer = createHttpServer(async (req, res) => {
      // CORS
      const origin = req.headers.origin ?? "";
      const allowedOrigin = ALLOWED_ORIGINS.has(origin) ? origin : "";
      if (allowedOrigin) {
        res.setHeader("Access-Control-Allow-Origin", allowedOrigin);
        res.setHeader("Vary", "Origin");
      }
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

      // MCP endpoint — create a fresh server per request, extract user's Bearer token
      if (req.url === "/mcp" || req.url === "/") {
        const authHeader = req.headers.authorization ?? "";
        const authToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : undefined;

        await requestContext.run({ authToken }, async () => {
          const server = createServer();
          const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
          res.on("close", () => { transport.close(); });
          await server.connect(transport);
          await transport.handleRequest(req, res);
        });
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
