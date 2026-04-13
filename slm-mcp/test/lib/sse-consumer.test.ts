import { describe, it, expect } from "vitest";
import { consumeSSEStream } from "../../src/lib/sse-consumer.js";

function makeSSEResponse(events: string[]): Response {
  const body = events.join("\n\n") + "\n\n";
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("consumeSSEStream", () => {
  it("collects text content from SSE events", async () => {
    const response = makeSSEResponse([
      'data: {"type":"text","content":"Hello "}',
      'data: {"type":"text","content":"world"}',
      "data: [DONE]",
    ]);

    const result = await consumeSSEStream(response);
    expect(result.text).toBe("Hello world");
  });

  it("extracts txData from structured events", async () => {
    const response = makeSSEResponse([
      'data: {"type":"txData","content":{"fee":5000,"slot":123}}',
      'data: {"type":"text","content":"A token transfer."}',
      "data: [DONE]",
    ]);

    const result = await consumeSSEStream(response);
    expect(result.txData).toEqual({ fee: 5000, slot: 123 });
    expect(result.text).toBe("A token transfer.");
  });

  it("extracts lookupData from structured events", async () => {
    const response = makeSSEResponse([
      'data: {"type":"lookupData","content":{"error_name":"ConstraintMut"}}',
      'data: {"type":"text","content":"Explanation here."}',
      "data: [DONE]",
    ]);

    const result = await consumeSSEStream(response);
    expect(result.lookupData).toEqual({ error_name: "ConstraintMut" });
    expect(result.text).toBe("Explanation here.");
  });

  it("handles empty stream gracefully", async () => {
    const response = makeSSEResponse(["data: [DONE]"]);

    const result = await consumeSSEStream(response);
    expect(result.text).toBe("");
  });

  it("ignores malformed SSE lines", async () => {
    const response = makeSSEResponse([
      "this is not a valid sse line",
      'data: {"type":"text","content":"valid"}',
      "data: [DONE]",
    ]);

    const result = await consumeSSEStream(response);
    expect(result.text).toBe("valid");
  });

  it("ignores SSE comments (lines starting with :)", async () => {
    const response = makeSSEResponse([
      ": this is a comment",
      'data: {"type":"text","content":"content"}',
      "data: [DONE]",
    ]);

    const result = await consumeSSEStream(response);
    expect(result.text).toBe("content");
  });
});
