export interface SSEResult {
  txData?: unknown;
  lookupData?: unknown;
  text: string;
}

interface SSEEvent {
  type: string;
  content: unknown;
}

function parseSSELine(line: string): SSEEvent | null {
  if (!line.startsWith("data: ")) return null;

  const data = line.slice(6).trim();
  if (data === "[DONE]") return null;

  try {
    return JSON.parse(data) as SSEEvent;
  } catch {
    return null;
  }
}

export async function consumeSSEStream(response: Response): Promise<SSEResult> {
  const body = await response.text();
  const lines = body.split("\n");

  const result: SSEResult = { text: "" };
  const textParts: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith(":")) continue;

    const event = parseSSELine(trimmed);
    if (!event) continue;

    switch (event.type) {
      case "text":
        textParts.push(event.content as string);
        break;
      case "txData":
        result.txData = event.content;
        break;
      case "lookupData":
        result.lookupData = event.content;
        break;
    }
  }

  result.text = textParts.join("");
  return result;
}
