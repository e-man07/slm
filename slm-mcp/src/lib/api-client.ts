import { API_BASE_URL } from "./constants.js";

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const apiKey = process.env.SLM_API_KEY;
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
    throw new Error(
      `Sealevel API error (${context}): ${response.status} ${response.statusText}${body ? ` - ${body}` : ""}`,
    );
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
  });

  await assertOk(response, "chat");
  const data = (await response.json()) as {
    choices?: Array<{ message: { content: string } }>;
    text?: string;
  };
  return data.choices?.[0]?.message?.content ?? data.text ?? "";
}

export async function callExplainTx(
  signature: string,
): Promise<{ txData: unknown; explanation: string }> {
  const response = await fetch(`${getBaseUrl()}/explain/tx`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ signature }),
  });

  await assertOk(response, "explain/tx");
  const data = (await response.json()) as {
    txData: unknown;
    explanation: string;
  };
  return data;
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
  });

  await assertOk(response, "explain/error");
  const data = (await response.json()) as {
    lookup: unknown;
    explanation: string;
  };
  return data;
}
