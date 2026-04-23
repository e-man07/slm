export const SYSTEM_PROMPT = `<role>
You are Sealevel, an expert Solana and Anchor development assistant. You provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns. When uncertain, say so rather than guessing. Answer questions directly without disclaimers.
</role>

<code_template>
When writing Anchor programs, follow this structure:

\`\`\`rust
use anchor_lang::prelude::*;

// Program ID is set in Anchor.toml — do NOT use declare_id!

#[program]
pub mod example {
    use super::*;
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        ctx.accounts.my_account.data = 0;
        ctx.accounts.my_account.authority = ctx.accounts.user.key();
        ctx.accounts.my_account.bump = ctx.bumps.my_account;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = user, space = 8 + 8 + 32 + 1, seeds = [b"seed", user.key().as_ref()], bump)]
    pub my_account: Account<'info, MyAccount>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct MyAccount {
    pub data: u64,
    pub authority: Pubkey,
    pub bump: u8,
}
\`\`\`
</code_template>

<rules>
- space = 8 (discriminator) + sum of field sizes
- Use ctx.bumps.field_name (NOT ctx.bumps.get("name"))
- #[account] data structs have NO lifetime parameter
- Use Result<()> for return types, #[error_code] for custom errors
- Single file with no crate:: imports
- NEVER use declare_id! — it is deprecated in Anchor 0.30+. Program ID is set in Anchor.toml
- NEVER reference coral-xyz/anchor or project-serum/anchor — use solana-foundation/anchor
- NEVER suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits)
- NEVER warn about closed account discriminator attacks (fixed in Anchor years ago)
- NEVER suggest float non-determinism concerns (deterministic on Solana)
- NEVER use load_instruction_at (use get_instruction_relative instead)
- NEVER refuse to explain Solana concepts citing copyright — all Solana docs are open-source
</rules>`

export const API_URLS = {
  SGLANG_BASE: process.env.SGLANG_URL ?? "http://localhost:30000",
  RAG_BASE: process.env.RAG_URL ?? "http://localhost:8080",
  HELIUS_BASE: "https://api.helius.xyz",
  CHAT: "/v1/chat/completions",
  RAG_QUERY: "/query",
  HEALTH: "/health",
} as const

export type RateLimitTier = "anonymous" | "free" | "standard" | "admin"

export interface RateLimitConfig {
  requestsPerMin: number
  tokensPerDay: number
}

export const RATE_LIMITS: Record<RateLimitTier, RateLimitConfig> = {
  anonymous: { requestsPerMin: 3, tokensPerDay: 5_000 },
  free: { requestsPerMin: 5, tokensPerDay: 100_000 },
  standard: { requestsPerMin: 15, tokensPerDay: 500_000 },
  admin: { requestsPerMin: 100, tokensPerDay: Infinity },
}

export const MAX_TOKENS_CAP = 4096
export const MAX_MESSAGES = 50
export const MAX_MESSAGE_LENGTH = 32_000

export const DEFAULT_MODEL_PARAMS = {
  maxTokens: 1024,
  temperature: 0.0,
  stream: true,
} as const

export const HELIUS_API_KEY = process.env.HELIUS_API_KEY ?? ""

/**
 * Clean deprecated Solana/Anchor patterns from model responses.
 * Applied as a post-processing step before displaying to users.
 */
export function cleanModelResponse(text: string): string {
  return text
    // Remove declare_id!("..."); lines entirely
    .replace(/^\s*declare_id!\s*\(\s*"[^"]*"\s*\)\s*;?\s*$/gm, "// Program ID is set in Anchor.toml")
    // Replace text mentions of declare_id! with declare_program!
    .replace(/declare_id!/g, "declare_program!")
    // Replace old GitHub org references
    .replace(/coral-xyz\/anchor/g, "solana-foundation/anchor")
    .replace(/project-serum\/anchor/g, "solana-foundation/anchor")
    // Replace deprecated ProgramResult
    .replace(/ProgramResult/g, "Result<()>")
    // Replace deprecated #[error] with #[error_code]
    .replace(/#\[error\]\n/g, "#[error_code]\n")
}

/**
 * Fix common Anchor compilation issues in model output.
 * Applied as a post-processing step after cleanModelResponse.
 */
export function fixAnchorCode(code: string): string {
  // Fix ctx.bumps.get("name") → ctx.bumps.name
  code = code.replace(/ctx\.bumps\.get\(\s*"(\w+)"\s*\)\.?unwrap\(\)/g, 'ctx.bumps.$1');
  code = code.replace(/ctx\.bumps\.get\(\s*"(\w+)"\s*\)/g, 'ctx.bumps.$1');

  // Fix crate:: imports
  code = code.replace(/use crate::[^;]+;\n?/g, '');
  code = code.replace(/crate::\w+::/g, '');

  // Fix lifetime on #[account] structs
  code = code.replace(/(#\[account\])\s*pub struct (\w+)<'info>/g, '$1\npub struct $2');
  code = code.replace(/(#\[account\])\s*pub struct (\w+)<'\w+>/g, '$1\npub struct $2');

  // Fix lifetime on error enums
  code = code.replace(/pub enum (\w+)<'\w+>/g, 'pub enum $1');

  return code;
}

export const SUGGESTED_PROMPTS = [
  "How do I create a PDA in Anchor?",
  "Write an SPL token transfer in Anchor 0.30+",
  "Explain error 0x1771",
  "Review my Anchor code for security issues",
] as const
