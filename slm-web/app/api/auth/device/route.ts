import { randomBytes } from "crypto"
import { getRedis } from "@/lib/redis"

/**
 * POST /api/auth/device — Initiate device auth flow.
 *
 * Returns a user code and verification URL. The CLI displays the code
 * and opens the URL in the user's browser. No authentication required.
 *
 * Response: { userCode, verificationUrl, expiresIn, interval }
 */
export async function POST() {
  const code = generateDeviceCode()
  const redis = getRedis()

  const payload = JSON.stringify({
    status: "pending",
    userId: null,
    apiKey: null,
  })

  await redis.set(`device:${code}`, payload, "EX", 600) // 10 min TTL

  return Response.json({
    userCode: code,
    verificationUrl: "https://sealevel.tech/device",
    expiresIn: 600,
    interval: 5,
  })
}

/**
 * Generate an 8-character device code in XXXX-XXXX format.
 * Uses only uppercase alphanumeric chars, avoiding ambiguous ones (0/O, 1/I/L).
 */
function generateDeviceCode(): string {
  const chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
  const bytes = randomBytes(8)
  let code = ""
  for (let i = 0; i < 8; i++) {
    code += chars[bytes[i] % chars.length]
  }
  return `${code.slice(0, 4)}-${code.slice(4)}`
}
