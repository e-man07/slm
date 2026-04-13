import { describe, it, expect, vi, afterEach } from "vitest";
import { handleMigrateCode } from "../../src/tools/migrate-code.js";

describe("handleMigrateCode", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("wraps code in migration prompt and returns response", async () => {
    let capturedBody = "";
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      capturedBody = init?.body as string;
      return new Response(
        JSON.stringify({ text: "Here is the migrated code..." }),
        { status: 200 },
      );
    }) as unknown as typeof fetch;

    const result = await handleMigrateCode({
      code: 'declare_id!("Fg6Pa");',
    });

    expect(result.content).toHaveLength(1);
    expect(result.content[0].text).toBe("Here is the migrated code...");

    // Verify the message sent to API contains migration context
    const body = JSON.parse(capturedBody);
    expect(body.message).toContain("migrate");
    expect(body.message).toContain('declare_id!("Fg6Pa")');
    expect(body.stream).toBe(false);
  });

  it("returns error on API failure", async () => {
    vi.stubEnv("SLM_API_URL", "https://test.slm.dev/api");

    globalThis.fetch = vi.fn(async () => {
      return new Response("Error", { status: 500 });
    }) as unknown as typeof fetch;

    const result = await handleMigrateCode({ code: "some code" });

    expect(result.content[0].text).toContain("Error");
    expect(result.isError).toBe(true);
  });
});
