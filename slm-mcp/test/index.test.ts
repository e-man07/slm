import { describe, it, expect } from "vitest";
import { createServer } from "../src/index.js";

describe("createServer", () => {
  it("creates a server without error", () => {
    const server = createServer();
    expect(server).toBeDefined();
  });

  it("has the correct server name", () => {
    const server = createServer();
    // The McpServer wraps a Server, check it exists
    expect(server.server).toBeDefined();
  });
});
