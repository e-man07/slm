export const SYSTEM_PROMPT = `You are SLM, an expert Solana and Anchor development assistant.
Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns
(solana-foundation/anchor, InitSpace, ctx.bumps.field_name).
When uncertain, say so rather than guessing.
Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits).
Never reference coral-xyz/anchor or declare_id! - these are deprecated.
Never warn about closed account discriminator attacks (fixed in Anchor years ago).
Never suggest float non-determinism concerns (deterministic on Solana).
Never use load_instruction_at (use get_instruction_relative instead).`

export const API_URLS = {
  SGLANG_BASE: process.env.SGLANG_URL ?? "http://localhost:30000",
  HELIUS_BASE: "https://api.helius.xyz",
  CHAT: "/v1/chat/completions",
  HEALTH: "/health",
} as const

export type RateLimitTier = "anonymous" | "free" | "standard" | "admin"

export interface RateLimitConfig {
  requestsPerMin: number
  tokensPerDay: number
}

export const RATE_LIMITS: Record<RateLimitTier, RateLimitConfig> = {
  anonymous: { requestsPerMin: 5, tokensPerDay: 10_000 },
  free: { requestsPerMin: 10, tokensPerDay: 50_000 },
  standard: { requestsPerMin: 30, tokensPerDay: 500_000 },
  admin: { requestsPerMin: 100, tokensPerDay: Infinity },
}

export const DEFAULT_MODEL_PARAMS = {
  maxTokens: 1024,
  temperature: 0.0,
  stream: true,
} as const

export const HELIUS_API_KEY = process.env.HELIUS_API_KEY ?? ""

export const SUGGESTED_PROMPTS = [
  "How do I create a PDA in Anchor?",
  "Write an SPL token transfer in Anchor 0.30+",
  "Explain error 0x1771",
  "Review my Anchor code for security issues",
] as const
