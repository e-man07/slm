import { API_URLS } from "@/lib/constants"

async function checkService(url: string): Promise<boolean> {
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) })
    return resp.ok
  } catch {
    return false
  }
}

export async function GET() {
  const [sglang, rag] = await Promise.all([
    // LiteLLM exposes /v1/models; use as health check
    checkService(`${API_URLS.SGLANG_BASE}/v1/models`),
    checkService(`${API_URLS.RAG_BASE}/health`),
  ])

  const allOk = sglang && rag

  return Response.json(
    {
      status: allOk ? "ok" : "degraded",
      services: { sglang, rag },
      timestamp: new Date().toISOString(),
    },
    { status: allOk ? 200 : 503 },
  )
}
