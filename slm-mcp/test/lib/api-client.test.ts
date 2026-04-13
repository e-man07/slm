import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { callChat, callExplainTx, callDecodeError } from "../../src/lib/api-client.js";

describe("api-client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.stubEnv("SLM_API_URL", "https://test-api.slm.dev/api");
    vi.stubEnv("SLM_API_KEY", "slm_testkey123");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  describe("callChat", () => {
    it("sends correct request body and returns text", async () => {
      let capturedUrl = "";
      let capturedInit: RequestInit | undefined;

      globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        capturedUrl = url.toString();
        capturedInit = init;
        return new Response(
          JSON.stringify({ text: "Hello from SLM" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }) as unknown as typeof fetch;

      const result = await callChat("What is a PDA?");

      expect(capturedUrl).toBe("https://test-api.slm.dev/api/chat");
      expect(capturedInit?.method).toBe("POST");
      const body = JSON.parse(capturedInit?.body as string);
      expect(body.message).toBe("What is a PDA?");
      expect(body.stream).toBe(false);
      expect(result).toBe("Hello from SLM");
    });

    it("includes context when provided", async () => {
      let capturedBody = "";
      globalThis.fetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
        capturedBody = init?.body as string;
        return new Response(
          JSON.stringify({ text: "response" }),
          { status: 200 },
        );
      }) as unknown as typeof fetch;

      await callChat("help", "some context");
      const body = JSON.parse(capturedBody);
      expect(body.context).toBe("some context");
    });

    it("includes auth header when API key is set", async () => {
      let capturedHeaders: HeadersInit | undefined;
      globalThis.fetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
        capturedHeaders = init?.headers;
        return new Response(JSON.stringify({ text: "ok" }), { status: 200 });
      }) as unknown as typeof fetch;

      await callChat("test");
      expect(capturedHeaders).toHaveProperty("Authorization", "Bearer slm_testkey123");
    });

    it("throws on non-200 response", async () => {
      globalThis.fetch = vi.fn(async () => {
        return new Response("Server Error", { status: 500 });
      }) as unknown as typeof fetch;

      await expect(callChat("test")).rejects.toThrow();
    });
  });

  describe("callExplainTx", () => {
    it("sends correct request with signature", async () => {
      let capturedUrl = "";
      let capturedBody = "";

      globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        capturedUrl = url.toString();
        capturedBody = init?.body as string;
        return new Response(
          JSON.stringify({ txData: { fee: 5000 }, explanation: "Token transfer" }),
          { status: 200 },
        );
      }) as unknown as typeof fetch;

      const result = await callExplainTx("5abc123");

      expect(capturedUrl).toBe("https://test-api.slm.dev/api/explain/tx");
      const body = JSON.parse(capturedBody);
      expect(body.signature).toBe("5abc123");
      expect(result.txData).toEqual({ fee: 5000 });
      expect(result.explanation).toBe("Token transfer");
    });
  });

  describe("callDecodeError", () => {
    it("sends correct request with error code", async () => {
      let capturedUrl = "";
      let capturedBody = "";

      globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        capturedUrl = url.toString();
        capturedBody = init?.body as string;
        return new Response(
          JSON.stringify({ lookup: { error_name: "ConstraintMut" }, explanation: "Mut violated" }),
          { status: 200 },
        );
      }) as unknown as typeof fetch;

      const result = await callDecodeError("0x7D0");

      expect(capturedUrl).toBe("https://test-api.slm.dev/api/explain/error");
      const body = JSON.parse(capturedBody);
      expect(body.code).toBe("0x7D0");
      expect(result.lookup).toEqual({ error_name: "ConstraintMut" });
      expect(result.explanation).toBe("Mut violated");
    });

    it("includes program_id when provided", async () => {
      let capturedBody = "";
      globalThis.fetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
        capturedBody = init?.body as string;
        return new Response(
          JSON.stringify({ lookup: {}, explanation: "" }),
          { status: 200 },
        );
      }) as unknown as typeof fetch;

      await callDecodeError("100", "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");
      const body = JSON.parse(capturedBody);
      expect(body.programId).toBe("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");
    });
  });
});
