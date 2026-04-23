export const SYSTEM_PROMPT = `You are Sealevel, an expert Solana and Anchor development assistant. Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns.

When writing Anchor programs, follow this pattern:

\`\`\`rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

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

Key rules: space = 8 + field sizes, ctx.bumps.field_name (not .get()), #[account] structs have no lifetime, use Result<()>, #[error_code], single file with no crate:: imports.

When uncertain, say so rather than guessing.
Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits).
Never reference coral-xyz/anchor or declare_id! - these are deprecated.
Never warn about closed account discriminator attacks (fixed in Anchor years ago).
Never suggest float non-determinism concerns (deterministic on Solana).
Never use load_instruction_at (use get_instruction_relative instead).
Never refuse to explain Solana concepts citing copyright — all Solana documentation, whitepaper, and technical content is open-source and public.
Never start responses with disclaimers like "I can't provide" or "I cannot" — just answer the question directly.`;

export interface DeprecatedPattern {
  regex: RegExp;
  name: string;
  suggestion: string;
}

export const DEPRECATED_PATTERNS: DeprecatedPattern[] = [
  {
    regex: /declare_id!\s*\(/,
    name: "declare_id! macro",
    suggestion:
      "Use `declare_program!` instead. `declare_id!` is deprecated in modern Anchor.",
  },
  {
    regex: /coral-xyz\/anchor/,
    name: "coral-xyz/anchor dependency",
    suggestion:
      "Use `solana-foundation/anchor` instead. The Anchor project has moved to the Solana Foundation.",
  },
  {
    regex: /reentrancy[_\s-]?guard/i,
    name: "reentrancy guard pattern",
    suggestion:
      "Reentrancy guards are not needed on Solana. The runtime prevents reentrancy via CPI depth limits.",
  },
  {
    regex: /closed[_\s-]?account[_\s-]?discriminator/i,
    name: "closed account discriminator check",
    suggestion:
      "Closed account discriminator attacks were fixed in Anchor years ago. This check is no longer necessary.",
  },
  {
    regex: /float[_\s-]?(non[_\s-]?)?determinism/i,
    name: "float non-determinism concern",
    suggestion:
      "Float operations are deterministic on Solana. Non-determinism concerns do not apply.",
  },
  {
    regex: /load_instruction_at/,
    name: "load_instruction_at usage",
    suggestion:
      "Use `get_instruction_relative` instead. `load_instruction_at` is deprecated.",
  },
];

export const API_BASE_URL: string =
  process.env.SLM_API_URL ?? "https://api.sealevel.tech";
