import { API_BASE_URL } from "./constants.js";
import { getRequestApiKey } from "./request-context.js";

/**
 * Clean deprecated Solana/Anchor patterns from model responses.
 * Applied as a post-processing step before returning to MCP clients.
 */
function cleanModelResponse(text: string): string {
  return text
    // Remove declare_id!("..."); lines entirely
    .replace(/^\s*declare_id!\s*\(\s*"[^"]*"\s*\)\s*;?\s*$/gm, "// Program ID is set in Anchor.toml")
    // Replace text mentions of declare_id! with declare_program!
    .replace(/declare_id!/g, "declare_program!")
    // Replace old GitHub org references
    .replace(/coral-xyz\/anchor/g, "solana-foundation/anchor")
    .replace(/project-serum\/anchor/g, "solana-foundation/anchor")
    // Replace deprecated ProgramResult
    .replace(/ProgramResult/g, "Result<()>")
    // Replace deprecated #[error] with #[error_code]
    .replace(/#\[error\]\n/g, "#[error_code]\n");
}

/**
 * Fix common Anchor compilation issues in model output.
 * Applied as a post-processing step after cleanModelResponse.
 */
function fixAnchorCode(code: string): string {
  // Fix ctx.bumps.get("name") → ctx.bumps.name
  code = code.replace(/ctx\.bumps\.get\(\s*"(\w+)"\s*\)\.?unwrap\(\)/g, 'ctx.bumps.$1');
  code = code.replace(/ctx\.bumps\.get\(\s*"(\w+)"\s*\)/g, 'ctx.bumps.$1');

  // Fix crate:: imports
  code = code.replace(/use crate::[^;]+;\n?/g, '');
  code = code.replace(/crate::\w+::/g, '');

  // Fix lifetime on #[account] structs
  code = code.replace(/(#\[account\])\s*pub struct (\w+)<'info>/g, '$1\npub struct $2');
  code = code.replace(/(#\[account\])\s*pub struct (\w+)<'\w+>/g, '$1\npub struct $2');

  // Fix lifetime on error enums
  code = code.replace(/pub enum (\w+)<'\w+>/g, 'pub enum $1');

  return code;
}

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-SLM-Source": "mcp",
  };
  const apiKey = getRequestApiKey();
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }
  return headers;
}

function getBaseUrl(): string {
  return process.env.SLM_API_URL ?? API_BASE_URL;
}

async function assertOk(response: Response, context: string): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    console.error(`API error (${context}): ${response.status} ${body}`);
    throw new Error(`Sealevel API error: ${response.status} ${response.statusText}`);
  }
}

export async function callChat(
  message: string,
  context?: string,
): Promise<string> {
  const userContent = context
    ? `${message}\n\nContext:\n${context}`
    : message;

  const response = await fetch(`${getBaseUrl()}/chat`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({
      messages: [{ role: "user", content: userContent }],
      stream: false,
      max_tokens: 1024,
      temperature: 0.0,
    }),
    signal: AbortSignal.timeout(30000),
  });

  await assertOk(response, "chat");
  const data = (await response.json()) as {
    choices?: Array<{ message: { content: string } }>;
    text?: string;
  };
  const raw = data.choices?.[0]?.message?.content ?? data.text ?? "";
  return fixAnchorCode(cleanModelResponse(raw));
}

export async function callExplainTx(
  signature: string,
): Promise<{ txData: unknown; explanation: string }> {
  const response = await fetch(`${getBaseUrl()}/explain/tx`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ signature }),
    signal: AbortSignal.timeout(30000),
  });

  await assertOk(response, "explain/tx");
  const data = (await response.json()) as {
    txData: unknown;
    explanation: string;
  };
  return { ...data, explanation: fixAnchorCode(cleanModelResponse(data.explanation)) };
}

export async function callDecodeError(
  code: string,
  programId?: string,
): Promise<{ lookup: unknown; explanation: string }> {
  const body: Record<string, unknown> = { code };
  if (programId) {
    body.programId = programId;
  }

  const response = await fetch(`${getBaseUrl()}/explain/error`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });

  await assertOk(response, "explain/error");
  const data = (await response.json()) as {
    lookup: unknown;
    explanation: string;
  };
  return { ...data, explanation: fixAnchorCode(cleanModelResponse(data.explanation)) };
}
