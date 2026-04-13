import { describe, it, expect, vi, afterEach } from "vitest";
import { handleChat } from "../../src/tools/chat.js";

describe("handleChat", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("returns response text from API", async () => {
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ text: "A PDA is a Program Derived Address." }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    const result = await handleChat({ message: "What is a PDA?" });

    expect(result.content).toHaveLength(1);
    expect(result.content[0].type).toBe("text");
    expect(result.content[0].text).toBe("A PDA is a Program Derived Address.");
  });

  it("passes context to API when provided", async () => {
    let capturedBody = "";
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      capturedBody = init?.body as string;
      return new Response(
        JSON.stringify({ text: "response" }),
        { status: 200 },
      );
    }) as unknown as typeof fetch;

    await handleChat({ message: "help", context: "anchor program" });
    const body = JSON.parse(capturedBody);
    expect(body.context).toBe("anchor program");
  });

  it("returns error message on API failure", async () => {
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async () => {
      return new Response("Internal Server Error", { status: 500 });
    }) as unknown as typeof fetch;

    const result = await handleChat({ message: "test" });

    expect(result.content[0].text).toContain("Error");
    expect(result.isError).toBe(true);
  });

  it("returns error message on network failure", async () => {
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async () => {
      throw new Error("Network unreachable");
    }) as unknown as typeof fetch;

    const result = await handleChat({ message: "test" });

    expect(result.content[0].text).toContain("Error");
    expect(result.isError).toBe(true);
  });
});
