import { AsyncLocalStorage } from "node:async_hooks";

interface RequestContext {
  /** Bearer token from the incoming MCP HTTP request */
  authToken: string | undefined;
}

export const requestContext = new AsyncLocalStorage<RequestContext>();

/**
 * Get the auth token for the current request.
 * Falls back to SLM_API_KEY env var (for stdio transport or if no header sent).
 */
export function getRequestApiKey(): string | undefined {
  return requestContext.getStore()?.authToken ?? process.env.SLM_API_KEY;
}
