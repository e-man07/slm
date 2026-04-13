import { describe, it, expect, vi, afterEach } from "vitest";
import { handleExplainTx } from "../../src/tools/explain-tx.js";

describe("handleExplainTx", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("returns formatted transaction explanation", async () => {
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          txData: { fee: 5000, slot: 123456 },
          explanation: "This transaction transfers 1 SOL.",
        }),
        { status: 200 },
      );
    }) as unknown as typeof fetch;

    const result = await handleExplainTx({ signature: "5abc123def" });

    expect(result.content).toHaveLength(1);
    const text = result.content[0].text;
    expect(text).toContain("5abc123def");
    expect(text).toContain("1 SOL");
  });

  it("sends correct signature in request body", async () => {
    let capturedBody = "";
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      capturedBody = init?.body as string;
      return new Response(
        JSON.stringify({ txData: {}, explanation: "ok" }),
        { status: 200 },
      );
    }) as unknown as typeof fetch;

    await handleExplainTx({ signature: "mysig123" });
    const body = JSON.parse(capturedBody);
    expect(body.signature).toBe("mysig123");
  });

  it("returns error on API failure", async () => {
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async () => {
      return new Response("Not Found", { status: 404 });
    }) as unknown as typeof fetch;

    const result = await handleExplainTx({ signature: "bad" });

    expect(result.content[0].text).toContain("Error");
    expect(result.isError).toBe(true);
  });
});
