import { API_URLS } from "@/lib/constants"

export async function GET() {
  let sglangOk = false

  try {
    const response = await fetch(`${API_URLS.SGLANG_BASE}${API_URLS.HEALTH}`, {
      signal: AbortSignal.timeout(5000),
    })
    sglangOk = response.ok
  } catch {
    sglangOk = false
  }

  return Response.json({
    status: sglangOk ? "ok" : "down",
    sglang: sglangOk,
    timestamp: new Date().toISOString(),
  })
}
