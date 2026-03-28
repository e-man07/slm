#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 1: CRUD, constraints, PDA, SPL tokens.

Uses parameterized templates to generate many high-quality variations.
Target: ~500 pairs from this file alone.
"""
import json, sys
from pathlib import Path
from itertools import product

sys.path.insert(0, str(Path(__file__).parent))
from schema import Record, write_jsonl

SYSTEM = "You are an expert Solana and Anchor developer. Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns."
OUT_DIR = Path(__file__).parent.parent / "data" / "processed"


def m(u, a):
    return json.dumps([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": u},
        {"role": "assistant", "content": a},
    ], ensure_ascii=False)


def rec(content, method="glan", category=""):
    meta = {"method": method, "collected_at": "2026-03-27"}
    if category:
        meta["category"] = category
    return Record(
        id=Record.make_id(content),
        source=f"synthetic/{method}",
        source_type="qa",
        content=content,
        language="rust",
        license="synthetic-claude",
        metadata=meta,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Entity definitions: (snake_name, display_name, fields_list, seeds_description)
# fields_list: [(field_name, rust_type, init_space_attr)]
# ═══════════════════════════════════════════════════════════════════════════════

ENTITIES = [
    ("user_profile", "user profile", [
        ("authority", "Pubkey", ""),
        ("username", "String", '#[max_len(32)]'),
        ("reputation", "u64", ""),
        ("created_at", "i64", ""),
    ]),
    ("game_state", "game state", [
        ("authority", "Pubkey", ""),
        ("level", "u8", ""),
        ("score", "u64", ""),
        ("is_active", "bool", ""),
    ]),
    ("token_vault", "token vault", [
        ("authority", "Pubkey", ""),
        ("mint", "Pubkey", ""),
        ("total_deposited", "u64", ""),
        ("bump", "u8", ""),
    ]),
    ("proposal", "governance proposal", [
        ("proposer", "Pubkey", ""),
        ("title", "String", '#[max_len(64)]'),
        ("description", "String", '#[max_len(256)]'),
        ("votes_for", "u64", ""),
        ("votes_against", "u64", ""),
        ("is_executed", "bool", ""),
    ]),
    ("listing", "marketplace listing", [
        ("seller", "Pubkey", ""),
        ("mint", "Pubkey", ""),
        ("price", "u64", ""),
        ("is_active", "bool", ""),
    ]),
    ("staking_pool", "staking pool", [
        ("authority", "Pubkey", ""),
        ("reward_mint", "Pubkey", ""),
        ("total_staked", "u64", ""),
        ("reward_rate", "u64", ""),
        ("last_update_time", "i64", ""),
    ]),
    ("auction", "auction", [
        ("creator", "Pubkey", ""),
        ("highest_bidder", "Pubkey", ""),
        ("highest_bid", "u64", ""),
        ("end_time", "i64", ""),
        ("is_settled", "bool", ""),
    ]),
    ("subscription", "subscription", [
        ("subscriber", "Pubkey", ""),
        ("plan", "u8", ""),
        ("start_time", "i64", ""),
        ("end_time", "i64", ""),
        ("is_active", "bool", ""),
    ]),
    ("config", "program config", [
        ("admin", "Pubkey", ""),
        ("fee_bps", "u16", ""),
        ("treasury", "Pubkey", ""),
        ("is_paused", "bool", ""),
    ]),
    ("reward_pool", "reward pool", [
        ("authority", "Pubkey", ""),
        ("reward_per_token", "u128", ""),
        ("total_staked", "u64", ""),
        ("last_update_slot", "u64", ""),
    ]),
    ("escrow", "escrow", [
        ("maker", "Pubkey", ""),
        ("taker", "Pubkey", ""),
        ("amount", "u64", ""),
        ("expiry", "i64", ""),
        ("is_completed", "bool", ""),
    ]),
    ("lending_pool", "lending pool", [
        ("authority", "Pubkey", ""),
        ("mint", "Pubkey", ""),
        ("total_deposits", "u64", ""),
        ("total_borrows", "u64", ""),
        ("interest_rate", "u64", ""),
    ]),
    ("nft_collection", "NFT collection", [
        ("authority", "Pubkey", ""),
        ("name", "String", '#[max_len(32)]'),
        ("symbol", "String", '#[max_len(10)]'),
        ("max_supply", "u32", ""),
        ("current_supply", "u32", ""),
        ("royalty_bps", "u16", ""),
    ]),
    ("dao_treasury", "DAO treasury", [
        ("authority", "Pubkey", ""),
        ("total_funds", "u64", ""),
        ("proposal_count", "u64", ""),
        ("member_count", "u32", ""),
    ]),
    ("order_book", "order book", [
        ("authority", "Pubkey", ""),
        ("base_mint", "Pubkey", ""),
        ("quote_mint", "Pubkey", ""),
        ("bid_count", "u32", ""),
        ("ask_count", "u32", ""),
    ]),
]


def struct_name(snake):
    return "".join(w.capitalize() for w in snake.split("_"))


def gen_fields_code(fields, indent=8):
    lines = []
    pad = " " * indent
    for fname, ftype, space_attr in fields:
        if space_attr:
            lines.append(f"{pad}{space_attr}")
        lines.append(f"{pad}pub {fname}: {ftype},")
    return "\n".join(lines)


def gen_init_space_size(fields):
    """Estimate INIT_SPACE works with derive macro."""
    return "8 + " + struct_name(fields[0][0].replace(fields[0][0], "")) + "::INIT_SPACE"


PAIRS = []

# ═══════════════════════════════════════════════════════════════════════════════
# Template 1: Initialize account with PDA
# ═══════════════════════════════════════════════════════════════════════════════

for snake, display, fields in ENTITIES:
    sn = struct_name(snake)
    authority_field = fields[0][0]  # first field is always authority/creator
    fields_code = gen_fields_code(fields)

    q = f"Write an Anchor program with an instruction to initialize a {display} account using a PDA seeded by the user's public key."
    a = f"""Here's an Anchor program that initializes a `{sn}` PDA account:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod {snake}_program {{
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {{
        let account = &mut ctx.accounts.{snake};
        account.{authority_field} = ctx.accounts.user.key();
        account.bump = ctx.bumps.{snake};
        Ok(())
    }}
}}

#[derive(Accounts)]
pub struct Initialize<'info> {{
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(
        init,
        payer = user,
        space = 8 + {sn}::INIT_SPACE,
        seeds = [b"{snake}", user.key().as_ref()],
        bump,
    )]
    pub {snake}: Account<'info, {sn}>,
    pub system_program: Program<'info, System>,
}}

#[account]
#[derive(InitSpace)]
pub struct {sn} {{
{fields_code}
    pub bump: u8,
}}
```

Key points:
- Uses `InitSpace` derive macro to auto-calculate account size
- PDA seeded with `b"{snake}"` + user pubkey ensures one account per user
- Stores the bump for later PDA verification
- `init` constraint handles account creation and rent payment"""

    PAIRS.append(("init-account", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 2: Update account with constraint checks
# ═══════════════════════════════════════════════════════════════════════════════

for snake, display, fields in ENTITIES:
    sn = struct_name(snake)
    auth_field = fields[0][0]
    # Pick a numeric field to update (skip first field which is authority)
    updatable = [(f, t) for f, t, _ in fields[1:] if t in ("u8", "u16", "u32", "u64", "u128", "i64", "bool")]
    if not updatable:
        continue
    uf, ut = updatable[0]

    q = f"Write an Anchor instruction to update the `{uf}` field on a {display} account, ensuring only the original {auth_field} can make changes."
    a = f"""```rust
#[program]
pub mod {snake}_program {{
    use super::*;

    pub fn update_{uf}(ctx: Context<Update{struct_name(uf)}>, new_value: {ut}) -> Result<()> {{
        let account = &mut ctx.accounts.{snake};
        account.{uf} = new_value;
        Ok(())
    }}
}}

#[derive(Accounts)]
pub struct Update{struct_name(uf)}<'info> {{
    #[account(
        mut,
        seeds = [b"{snake}", {auth_field}.key().as_ref()],
        bump = {snake}.bump,
        has_one = {auth_field},
    )]
    pub {snake}: Account<'info, {sn}>,
    pub {auth_field}: Signer<'info>,
}}
```

The `has_one = {auth_field}` constraint verifies that `{snake}.{auth_field}` matches the `{auth_field}` account passed in. Combined with `Signer<'info>`, this ensures only the original {auth_field} can update the {uf} field. The PDA seeds and bump are re-verified to prevent account substitution."""

    PAIRS.append(("update-account", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 3: Close account and reclaim rent
# ═══════════════════════════════════════════════════════════════════════════════

for snake, display, fields in ENTITIES:
    sn = struct_name(snake)
    auth_field = fields[0][0]

    q = f"How do I close a {display} account in Anchor and return the rent to the {auth_field}?"
    a = f"""Use the `close` constraint to close the account and transfer lamports:

```rust
#[derive(Accounts)]
pub struct Close{sn}<'info> {{
    #[account(
        mut,
        seeds = [b"{snake}", {auth_field}.key().as_ref()],
        bump = {snake}.bump,
        has_one = {auth_field},
        close = {auth_field},
    )]
    pub {snake}: Account<'info, {sn}>,
    #[account(mut)]
    pub {auth_field}: Signer<'info>,
}}
```

The `close = {auth_field}` constraint:
1. Transfers all lamports from the {snake} account to {auth_field}
2. Zeros out the account data
3. Sets the account owner to the system program
4. This happens automatically at the end of the instruction — no manual code needed

Always include `has_one = {auth_field}` to prevent unauthorized closures."""

    PAIRS.append(("close-account", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 4: Realloc account (grow/shrink)
# ═══════════════════════════════════════════════════════════════════════════════

string_entities = [(s, d, f) for s, d, f in ENTITIES if any(t == "String" for _, t, _ in f)]

for snake, display, fields in string_entities:
    sn = struct_name(snake)
    auth_field = fields[0][0]
    str_field = next(f for f, t, _ in fields if t == "String")

    q = f"How do I resize a {display} account in Anchor when the {str_field} field needs more space?"
    a = f"""Use the `realloc` constraint to dynamically resize accounts:

```rust
#[derive(Accounts)]
pub struct Resize{sn}<'info> {{
    #[account(
        mut,
        seeds = [b"{snake}", {auth_field}.key().as_ref()],
        bump = {snake}.bump,
        has_one = {auth_field},
        realloc = 8 + {sn}::INIT_SPACE,
        realloc::payer = {auth_field},
        realloc::zero = false,
    )]
    pub {snake}: Account<'info, {sn}>,
    #[account(mut)]
    pub {auth_field}: Signer<'info>,
    pub system_program: Program<'info, System>,
}}
```

Notes:
- `realloc` recalculates the required space based on current `INIT_SPACE`
- `realloc::payer` pays additional rent if the account grows
- `realloc::zero = false` preserves existing data (set to `true` to zero new bytes)
- If the account shrinks, excess lamports are returned to the payer
- The system program is required for potential transfers"""

    PAIRS.append(("realloc", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 5: PDA with various seed combinations
# ═══════════════════════════════════════════════════════════════════════════════

SEED_COMBOS = [
    ("string + pubkey", '[b"vault", authority.key().as_ref()]',
     "a string literal and the authority's public key",
     '#[instruction()]\npub struct CreateVault'),
    ("string + pubkey + u64", '[b"order", user.key().as_ref(), &order_id.to_le_bytes()]',
     "a string literal, user pubkey, and a u64 order ID",
     '#[instruction(order_id: u64)]\npub struct CreateOrder'),
    ("string + two pubkeys", '[b"trade", maker.key().as_ref(), taker.key().as_ref()]',
     "a string literal and two public keys (maker and taker)",
     '#[instruction()]\npub struct CreateTrade'),
    ("string + pubkey + u8", '[b"level", player.key().as_ref(), &[level]]',
     "a string, player pubkey, and a u8 level number",
     '#[instruction(level: u8)]\npub struct CreateLevel'),
    ("string + mint + pubkey", '[b"position", mint.key().as_ref(), owner.key().as_ref()]',
     "a string, mint address, and owner pubkey",
     '#[instruction()]\npub struct CreatePosition'),
    ("string + string", '[b"config", b"main"]',
     "two string literals for a singleton config PDA",
     '#[instruction()]\npub struct InitConfig'),
    ("string + pubkey + i64", '[b"schedule", authority.key().as_ref(), &timestamp.to_le_bytes()]',
     "a string, authority pubkey, and an i64 timestamp",
     '#[instruction(timestamp: i64)]\npub struct CreateSchedule'),
    ("string + u16 + pubkey", '[b"pool", &pool_id.to_le_bytes(), authority.key().as_ref()]',
     "a string, u16 pool ID, and authority pubkey",
     '#[instruction(pool_id: u16)]\npub struct CreatePool'),
]

for desc, seeds_code, seeds_desc, struct_hint in SEED_COMBOS:
    q = f"How do I create a PDA in Anchor using {seeds_desc} as seeds?"
    a = f"""Use the `seeds` constraint with the appropriate byte conversions:

```rust
#[derive(Accounts)]
{struct_hint}<'info> {{
    #[account(
        init,
        payer = payer,
        space = 8 + 256,
        seeds = {seeds_code},
        bump,
    )]
    pub account: Account<'info, DataAccount>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}}
```

Seed encoding rules:
- `&[u8]` / `&str` → use directly or `b"literal"`
- `Pubkey` → `.key().as_ref()` (returns `&[u8; 32]`)
- `u64` / `i64` → `.to_le_bytes()` (returns `[u8; 8]`)
- `u32` / `i32` → `.to_le_bytes()` (returns `[u8; 4]`)
- `u16` → `.to_le_bytes()` (returns `[u8; 2]`)
- `u8` → `&[value]` (wraps in a single-byte slice)

Always store the bump in the account for efficient re-derivation."""

    PAIRS.append(("pda-seeds", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 6: SPL Token operations via CPI
# ═══════════════════════════════════════════════════════════════════════════════

TOKEN_OPS = [
    ("mint_to", "mint tokens to a user's associated token account",
     "MintTo", "mint_to",
     """pub fn mint_tokens(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
        let cpi_accounts = MintTo {
            mint: ctx.accounts.mint.to_account_info(),
            to: ctx.accounts.token_account.to_account_info(),
            authority: ctx.accounts.mint_authority.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        token::mint_to(CpiContext::new(cpi_program, cpi_accounts), amount)?;
        Ok(())
    }""",
     """#[derive(Accounts)]
pub struct MintTokens<'info> {
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    pub mint_authority: Signer<'info>,
    pub token_program: Program<'info, Token>,
}"""),
    ("transfer", "transfer SPL tokens between two token accounts",
     "Transfer", "transfer",
     """pub fn transfer_tokens(ctx: Context<TransferTokens>, amount: u64) -> Result<()> {
        let cpi_accounts = Transfer {
            from: ctx.accounts.from.to_account_info(),
            to: ctx.accounts.to.to_account_info(),
            authority: ctx.accounts.authority.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        token::transfer(CpiContext::new(cpi_program, cpi_accounts), amount)?;
        Ok(())
    }""",
     """#[derive(Accounts)]
pub struct TransferTokens<'info> {
    #[account(mut)]
    pub from: Account<'info, TokenAccount>,
    #[account(mut)]
    pub to: Account<'info, TokenAccount>,
    pub authority: Signer<'info>,
    pub token_program: Program<'info, Token>,
}"""),
    ("burn", "burn SPL tokens from a token account",
     "Burn", "burn",
     """pub fn burn_tokens(ctx: Context<BurnTokens>, amount: u64) -> Result<()> {
        let cpi_accounts = Burn {
            mint: ctx.accounts.mint.to_account_info(),
            from: ctx.accounts.token_account.to_account_info(),
            authority: ctx.accounts.authority.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        token::burn(CpiContext::new(cpi_program, cpi_accounts), amount)?;
        Ok(())
    }""",
     """#[derive(Accounts)]
pub struct BurnTokens<'info> {
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    pub authority: Signer<'info>,
    pub token_program: Program<'info, Token>,
}"""),
    ("approve", "approve a delegate to spend SPL tokens",
     "Approve", "approve",
     """pub fn approve_delegate(ctx: Context<ApproveDelegate>, amount: u64) -> Result<()> {
        let cpi_accounts = Approve {
            to: ctx.accounts.token_account.to_account_info(),
            delegate: ctx.accounts.delegate.to_account_info(),
            authority: ctx.accounts.owner.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        token::approve(CpiContext::new(cpi_program, cpi_accounts), amount)?;
        Ok(())
    }""",
     """#[derive(Accounts)]
pub struct ApproveDelegate<'info> {
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    /// CHECK: delegate can be any account
    pub delegate: UncheckedAccount<'info>,
    pub owner: Signer<'info>,
    pub token_program: Program<'info, Token>,
}"""),
    ("freeze", "freeze a token account to prevent transfers",
     "FreezeAccount", "freeze_account",
     """pub fn freeze(ctx: Context<FreezeTokenAccount>) -> Result<()> {
        let cpi_accounts = FreezeAccount {
            account: ctx.accounts.token_account.to_account_info(),
            mint: ctx.accounts.mint.to_account_info(),
            authority: ctx.accounts.freeze_authority.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        token::freeze_account(CpiContext::new(cpi_program, cpi_accounts))?;
        Ok(())
    }""",
     """#[derive(Accounts)]
pub struct FreezeTokenAccount<'info> {
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    pub freeze_authority: Signer<'info>,
    pub token_program: Program<'info, Token>,
}"""),
    ("close_account", "close a token account and reclaim rent",
     "CloseAccount", "close_account",
     """pub fn close_token_account(ctx: Context<CloseTokenAcc>) -> Result<()> {
        let cpi_accounts = CloseAccount {
            account: ctx.accounts.token_account.to_account_info(),
            destination: ctx.accounts.destination.to_account_info(),
            authority: ctx.accounts.owner.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        token::close_account(CpiContext::new(cpi_program, cpi_accounts))?;
        Ok(())
    }""",
     """#[derive(Accounts)]
pub struct CloseTokenAcc<'info> {
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    /// CHECK: destination receives lamports
    pub destination: UncheckedAccount<'info>,
    pub owner: Signer<'info>,
    pub token_program: Program<'info, Token>,
}"""),
]

for op_name, desc, cpi_struct, cpi_fn, fn_code, accounts_code in TOKEN_OPS:
    q = f"How do I {desc} in an Anchor program using CPI?"
    a = f"""Use `anchor_spl::token` for SPL token CPI calls:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{{self, {cpi_struct}, Mint, Token, TokenAccount}};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod token_ops {{
    use super::*;

    {fn_code}
}}

{accounts_code}
```

The `token::{cpi_fn}` function creates a CPI call to the SPL Token program. The `CpiContext::new` wraps the program and accounts. For PDA-signed operations, use `CpiContext::new_with_signer` with the PDA seeds."""

    PAIRS.append(("spl-token", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 7: PDA-signed CPI (token operations with program authority)
# ═══════════════════════════════════════════════════════════════════════════════

PDA_CPI_OPS = [
    ("mint tokens using a PDA mint authority",
     """pub fn pda_mint(ctx: Context<PdaMint>, amount: u64) -> Result<()> {
        let seeds = &[b"mint-authority".as_ref(), &[ctx.accounts.vault.bump]];
        let signer_seeds = &[&seeds[..]];

        let cpi_accounts = MintTo {
            mint: ctx.accounts.mint.to_account_info(),
            to: ctx.accounts.destination.to_account_info(),
            authority: ctx.accounts.vault.to_account_info(),
        };
        token::mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                cpi_accounts,
                signer_seeds,
            ),
            amount,
        )?;
        Ok(())
    }"""),
    ("transfer tokens from a PDA-owned token account",
     """pub fn pda_transfer(ctx: Context<PdaTransfer>, amount: u64) -> Result<()> {
        let seeds = &[
            b"vault".as_ref(),
            ctx.accounts.authority.key.as_ref(),
            &[ctx.accounts.vault_state.bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let cpi_accounts = Transfer {
            from: ctx.accounts.vault_token.to_account_info(),
            to: ctx.accounts.user_token.to_account_info(),
            authority: ctx.accounts.vault_state.to_account_info(),
        };
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                cpi_accounts,
                signer_seeds,
            ),
            amount,
        )?;
        Ok(())
    }"""),
    ("burn tokens from a PDA-controlled token account",
     """pub fn pda_burn(ctx: Context<PdaBurn>, amount: u64) -> Result<()> {
        let seeds = &[
            b"burner".as_ref(),
            ctx.accounts.mint.key().as_ref(),
            &[ctx.accounts.burn_authority.bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let cpi_accounts = Burn {
            mint: ctx.accounts.mint.to_account_info(),
            from: ctx.accounts.token_account.to_account_info(),
            authority: ctx.accounts.burn_authority.to_account_info(),
        };
        token::burn(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                cpi_accounts,
                signer_seeds,
            ),
            amount,
        )?;
        Ok(())
    }"""),
]

for desc, fn_code in PDA_CPI_OPS:
    q = f"How do I {desc} in Anchor?"
    a = f"""Use `CpiContext::new_with_signer` with the PDA's seeds:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{{self, Burn, MintTo, Transfer, Mint, Token, TokenAccount}};

#[program]
pub mod pda_cpi_example {{
    use super::*;

    {fn_code}
}}
```

Key pattern for PDA-signed CPI:
1. Reconstruct the PDA seeds including the stored bump
2. Wrap in `&[&seeds[..]]` for the signer seeds slice
3. Pass to `CpiContext::new_with_signer` instead of `CpiContext::new`
4. The runtime verifies the seeds derive to the signing PDA"""

    PAIRS.append(("pda-cpi", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 8: Custom errors
# ═══════════════════════════════════════════════════════════════════════════════

ERROR_SETS = [
    ("staking", [
        ("InsufficientStake", "Attempted to unstake more than staked balance"),
        ("StakingPaused", "The staking pool is currently paused"),
        ("LockupNotExpired", "Tokens are still locked and cannot be withdrawn"),
        ("InvalidRewardRate", "Reward rate must be greater than zero"),
        ("PoolFull", "The staking pool has reached maximum capacity"),
    ]),
    ("marketplace", [
        ("ListingNotActive", "This listing has already been sold or cancelled"),
        ("PriceMismatch", "The payment amount does not match the listing price"),
        ("SellerCannotBuy", "Sellers cannot purchase their own listings"),
        ("InvalidRoyalty", "Royalty basis points must be between 0 and 10000"),
        ("CollectionMismatch", "The NFT does not belong to the expected collection"),
    ]),
    ("governance", [
        ("VotingEnded", "The voting period has ended"),
        ("AlreadyVoted", "This wallet has already voted on this proposal"),
        ("QuorumNotReached", "The proposal has not reached the required quorum"),
        ("ProposalExecuted", "This proposal has already been executed"),
        ("InsufficientVotingPower", "Insufficient token balance for voting"),
    ]),
    ("lending", [
        ("InsufficientCollateral", "Collateral ratio is below the minimum threshold"),
        ("MaxBorrowExceeded", "Borrow amount exceeds the maximum allowed"),
        ("LiquidationNotAllowed", "Position is still healthy and cannot be liquidated"),
        ("OraclePriceStale", "The oracle price feed is outdated"),
        ("MarketFrozen", "This lending market is temporarily frozen"),
    ]),
    ("auction", [
        ("AuctionNotStarted", "The auction has not started yet"),
        ("AuctionEnded", "The auction has already ended"),
        ("BidTooLow", "Bid must be higher than the current highest bid"),
        ("CannotBidOnOwnAuction", "Auction creators cannot bid on their own auctions"),
        ("AuctionNotSettled", "The auction must be settled before claiming"),
    ]),
    ("token_launch", [
        ("SaleNotStarted", "The token sale has not started yet"),
        ("SaleEnded", "The token sale has ended"),
        ("HardCapReached", "The hard cap has been reached"),
        ("BelowMinPurchase", "Purchase amount is below the minimum"),
        ("AboveMaxPurchase", "Purchase amount exceeds the per-wallet maximum"),
        ("VestingNotStarted", "Token vesting has not begun yet"),
    ]),
]

for domain, errors in ERROR_SETS:
    sn = struct_name(domain)
    errors_code = "\n".join(f'    #[msg("{msg}")]\n    {name},' for name, msg in errors)

    q = f"What custom errors should I define for a {domain} program in Anchor?"
    a = f"""Define errors using the `#[error_code]` attribute macro:

```rust
use anchor_lang::prelude::*;

#[error_code]
pub enum {sn}Error {{
{errors_code}
}}
```

Usage in instructions:

```rust
// Using require! macro (preferred for boolean checks)
require!(condition, {sn}Error::{errors[0][0]});

// Using err! macro (for complex conditions)
if !condition {{
    return err!({sn}Error::{errors[1][0]});
}}

// Using constraint in account validation
#[account(
    constraint = some_check @ {sn}Error::{errors[2][0]}
)]
```

Best practices:
- Use descriptive `#[msg]` attributes — they appear in transaction logs
- Anchor auto-assigns error codes starting at 6000
- Use `require!` for simple checks, `err!` for complex logic branches
- Reference errors in `constraint = ... @ ErrorName` for account-level validation"""

    PAIRS.append(("errors", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 9: Events
# ═══════════════════════════════════════════════════════════════════════════════

EVENT_DEFS = [
    ("deposit", [("user", "Pubkey"), ("amount", "u64"), ("vault", "Pubkey")],
     "a deposit into a vault"),
    ("withdrawal", [("user", "Pubkey"), ("amount", "u64"), ("remaining", "u64")],
     "a withdrawal from a vault"),
    ("trade", [("maker", "Pubkey"), ("taker", "Pubkey"), ("amount_in", "u64"), ("amount_out", "u64"), ("price", "u64")],
     "a trade execution"),
    ("stake", [("user", "Pubkey"), ("amount", "u64"), ("pool", "Pubkey"), ("total_staked", "u64")],
     "staking tokens"),
    ("vote", [("voter", "Pubkey"), ("proposal_id", "u64"), ("vote_weight", "u64"), ("in_favor", "bool")],
     "casting a governance vote"),
    ("listing_created", [("seller", "Pubkey"), ("mint", "Pubkey"), ("price", "u64"), ("listing_id", "u64")],
     "creating a marketplace listing"),
    ("bid_placed", [("bidder", "Pubkey"), ("auction", "Pubkey"), ("amount", "u64"), ("timestamp", "i64")],
     "placing an auction bid"),
    ("loan_issued", [("borrower", "Pubkey"), ("amount", "u64"), ("collateral", "u64"), ("interest_rate", "u64")],
     "issuing a loan"),
    ("liquidation", [("liquidator", "Pubkey"), ("borrower", "Pubkey"), ("repaid", "u64"), ("seized", "u64")],
     "liquidating a position"),
    ("reward_claimed", [("user", "Pubkey"), ("amount", "u64"), ("epoch", "u64")],
     "claiming rewards"),
]

for event_name, event_fields, desc in EVENT_DEFS:
    sn = struct_name(event_name)
    fields_str = "\n".join(f"    pub {f}: {t}," for f, t in event_fields)
    emit_fields = ", ".join(f"{f}: value_{f}" for f, _ in event_fields)

    q = f"How do I emit an event in Anchor when {desc}?"
    a = f"""Define an event struct with `#[event]` and emit it with `emit!`:

```rust
use anchor_lang::prelude::*;

#[event]
pub struct {sn}Event {{
{fields_str}
}}

// In your instruction handler:
pub fn handle_{event_name}(ctx: Context<Handle{sn}>) -> Result<()> {{
    // ... business logic ...

    emit!({sn}Event {{
        {", ".join(f'{f}: {f}_value' for f, _ in event_fields)},
    }});

    Ok(())
}}
```

Events are logged to the transaction log via `sol_log_data`. Clients can subscribe using:

```typescript
program.addEventListener("{event_name.replace('_', '')}", (event, slot) => {{
    console.log("Event:", event);
}});
```

Notes:
- Events are not stored on-chain — they're in transaction logs only
- Use `anchor events` to view events in local testing
- Client-side, events can be parsed from transaction logs or received via WebSocket subscription"""

    PAIRS.append(("events", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 10: Constraint expressions
# ═══════════════════════════════════════════════════════════════════════════════

CONSTRAINTS = [
    ("an amount is positive", 'constraint = amount > 0 @ MyError::InvalidAmount',
     "The `constraint` attribute accepts any boolean Rust expression."),
    ("two accounts have matching mints", 'constraint = source.mint == destination.mint @ MyError::MintMismatch',
     "Compare `mint` fields across token accounts to prevent cross-mint transfers."),
    ("a timestamp hasn't expired", 'constraint = Clock::get()?.unix_timestamp < account.expiry @ MyError::Expired',
     "Access the clock via `Clock::get()?` directly in constraints."),
    ("a token account has sufficient balance", 'constraint = token_account.amount >= required_amount @ MyError::InsufficientBalance',
     "Access `TokenAccount` fields like `amount`, `mint`, `owner` directly."),
    ("an account is not frozen", 'constraint = !config.is_paused @ MyError::ProgramPaused',
     "Use boolean fields in config accounts for global pause functionality."),
    ("a user is the token account owner", 'constraint = token_account.owner == user.key() @ MyError::Unauthorized',
     "Verify token account ownership instead of relying solely on the signer check."),
    ("a price is within bounds", 'constraint = price >= min_price && price <= max_price @ MyError::PriceOutOfRange',
     "Compound expressions with `&&` and `||` work in constraints."),
    ("two keys are different", 'constraint = account_a.key() != account_b.key() @ MyError::DuplicateAccounts',
     "Prevent passing the same account twice when two distinct accounts are required."),
]

for desc, constraint_code, explanation in CONSTRAINTS:
    q = f"How do I add an Anchor constraint that checks {desc}?"
    a = f"""Use the `constraint` attribute with a custom error:

```rust
#[derive(Accounts)]
pub struct MyInstruction<'info> {{
    #[account(
        mut,
        {constraint_code},
    )]
    pub account: Account<'info, MyAccount>,
    // ... other accounts
}}
```

{explanation}

The constraint is evaluated before the instruction handler runs, so invalid states are rejected early. Always use a custom error (`@ MyError::Name`) for clear error messages instead of generic constraint failures."""

    PAIRS.append(("constraints", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 11: Associated Token Account patterns
# ═══════════════════════════════════════════════════════════════════════════════

ATA_PATTERNS = [
    ("init_if_needed", "initialize an associated token account only if it doesn't already exist",
     """#[derive(Accounts)]
pub struct CreateAta<'info> {
    #[account(
        init_if_needed,
        payer = payer,
        associated_token::mint = mint,
        associated_token::authority = owner,
    )]
    pub token_account: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    /// CHECK: ATA owner
    pub owner: UncheckedAccount<'info>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
}""",
     "`init_if_needed` is safe for ATAs because the address is deterministic. Add `anchor-lang = { features = [\"init-if-needed\"] }` to Cargo.toml."),
    ("init", "always create a new associated token account",
     """#[derive(Accounts)]
pub struct CreateAta<'info> {
    #[account(
        init,
        payer = payer,
        associated_token::mint = mint,
        associated_token::authority = owner,
    )]
    pub token_account: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    /// CHECK: ATA owner
    pub owner: UncheckedAccount<'info>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
}""",
     "Use `init` when you expect the ATA to not exist. The instruction will fail if it already exists."),
    ("validate_existing", "validate that an existing ATA matches expected mint and owner",
     """#[derive(Accounts)]
pub struct UseAta<'info> {
    #[account(
        mut,
        associated_token::mint = mint,
        associated_token::authority = owner,
    )]
    pub token_account: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    pub owner: Signer<'info>,
}""",
     "Without `init`, Anchor just validates that the token account is the correct ATA for the given mint and owner."),
]

for pattern, desc, code, explanation in ATA_PATTERNS:
    q = f"How do I {desc} in Anchor?"
    a = f"""```rust
use anchor_lang::prelude::*;
use anchor_spl::{{
    token::{{Token, TokenAccount, Mint}},
    associated_token::AssociatedToken,
}};

{code}
```

{explanation}

The associated token account address is derived deterministically from the mint and owner, so there's exactly one ATA per (owner, mint) pair."""

    PAIRS.append(("ata", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 12: Checked math operations
# ═══════════════════════════════════════════════════════════════════════════════

MATH_OPS = [
    ("calculate fees with basis points",
     """pub fn calculate_fee(amount: u64, fee_bps: u16) -> Result<u64> {
    let fee = (amount as u128)
        .checked_mul(fee_bps as u128)
        .ok_or(MyError::MathOverflow)?
        .checked_div(10_000)
        .ok_or(MyError::MathOverflow)? as u64;
    Ok(fee)
}""",
     "Use u128 intermediate to prevent overflow on large amounts. BPS = basis points (1 BPS = 0.01%)."),
    ("safely compute rewards over time",
     """pub fn compute_rewards(
    staked: u64,
    rate_per_second: u64,
    elapsed_seconds: i64,
) -> Result<u64> {
    require!(elapsed_seconds >= 0, MyError::InvalidTime);
    let reward = (staked as u128)
        .checked_mul(rate_per_second as u128)
        .ok_or(MyError::MathOverflow)?
        .checked_mul(elapsed_seconds as u128)
        .ok_or(MyError::MathOverflow)?
        .checked_div(1_000_000_000) // precision factor
        .ok_or(MyError::MathOverflow)?;
    require!(reward <= u64::MAX as u128, MyError::MathOverflow);
    Ok(reward as u64)
}""",
     "Chain `checked_*` operations and propagate errors. Use a precision factor to maintain accuracy without floats."),
    ("compute a weighted average price",
     """pub fn weighted_avg_price(
    old_amount: u64, old_price: u64,
    new_amount: u64, new_price: u64,
) -> Result<u64> {
    let old_value = (old_amount as u128).checked_mul(old_price as u128)
        .ok_or(MyError::MathOverflow)?;
    let new_value = (new_amount as u128).checked_mul(new_price as u128)
        .ok_or(MyError::MathOverflow)?;
    let total_amount = (old_amount as u128).checked_add(new_amount as u128)
        .ok_or(MyError::MathOverflow)?;
    require!(total_amount > 0, MyError::DivisionByZero);
    let avg = old_value.checked_add(new_value)
        .ok_or(MyError::MathOverflow)?
        .checked_div(total_amount)
        .ok_or(MyError::MathOverflow)?;
    Ok(avg as u64)
}""",
     "Always check for zero divisors. Use u128 for intermediate multiplication to prevent overflow."),
    ("calculate proportional share of a pool",
     """pub fn calculate_share(
    user_stake: u64,
    total_staked: u64,
    pool_balance: u64,
) -> Result<u64> {
    require!(total_staked > 0, MyError::EmptyPool);
    let share = (user_stake as u128)
        .checked_mul(pool_balance as u128)
        .ok_or(MyError::MathOverflow)?
        .checked_div(total_staked as u128)
        .ok_or(MyError::MathOverflow)?;
    Ok(share as u64)
}""",
     "Classic proportional share calculation: user_share = (user_stake * pool_balance) / total_staked. Guard against empty pool."),
    ("convert between token decimals",
     """pub fn convert_decimals(
    amount: u64,
    from_decimals: u8,
    to_decimals: u8,
) -> Result<u64> {
    if from_decimals == to_decimals {
        return Ok(amount);
    }
    let result = if to_decimals > from_decimals {
        let factor = 10u64.checked_pow((to_decimals - from_decimals) as u32)
            .ok_or(MyError::MathOverflow)?;
        amount.checked_mul(factor).ok_or(MyError::MathOverflow)?
    } else {
        let factor = 10u64.checked_pow((from_decimals - to_decimals) as u32)
            .ok_or(MyError::MathOverflow)?;
        amount.checked_div(factor).ok_or(MyError::MathOverflow)?
    };
    Ok(result)
}""",
     "Handle both scaling up and down. Be aware that scaling down loses precision (truncation)."),
]

for desc, code, explanation in MATH_OPS:
    q = f"How do I {desc} safely in a Solana program?"
    a = f"""Use checked arithmetic to prevent overflow/underflow:

```rust
{code}
```

{explanation}

**Important:** Never use regular `+`, `-`, `*`, `/` operators in Solana programs — an overflow will cause undefined behavior. Always use `checked_add`, `checked_sub`, `checked_mul`, `checked_div`, or `saturating_*` variants. Solana does NOT have the same overflow checks as standard Rust (programs compile with overflow checks disabled)."""

    PAIRS.append(("math", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 13: Access control patterns
# ═══════════════════════════════════════════════════════════════════════════════

ACCESS_PATTERNS = [
    ("single admin", "restrict an instruction to a single admin",
     """#[derive(Accounts)]
pub struct AdminOnly<'info> {
    #[account(
        mut,
        has_one = admin @ MyError::Unauthorized,
    )]
    pub config: Account<'info, Config>,
    pub admin: Signer<'info>,
}""",
     "Store the admin pubkey in a config PDA. `has_one` checks that `config.admin == admin.key()`."),
    ("role-based", "implement role-based access control",
     """#[account]
#[derive(InitSpace)]
pub struct AccessControl {
    pub super_admin: Pubkey,
    pub operators: [Pubkey; 5],
    pub operator_count: u8,
}

pub fn is_operator(access: &AccessControl, key: &Pubkey) -> bool {
    access.operators[..access.operator_count as usize]
        .iter()
        .any(|op| op == key)
}

#[derive(Accounts)]
pub struct OperatorAction<'info> {
    #[account(
        constraint = is_operator(&access_control, &operator.key()) @ MyError::NotOperator,
    )]
    pub access_control: Account<'info, AccessControl>,
    pub operator: Signer<'info>,
}""",
     "Use a fixed-size array for roles. For dynamic roles, consider a separate PDA per (role, user) pair."),
    ("time-locked", "add a time-lock to sensitive operations",
     """#[account]
#[derive(InitSpace)]
pub struct TimeLock {
    pub admin: Pubkey,
    pub pending_action: u8,
    pub execute_after: i64,
    pub bump: u8,
}

pub fn execute_timelocked(ctx: Context<ExecuteTimelocked>) -> Result<()> {
    let timelock = &ctx.accounts.timelock;
    let clock = Clock::get()?;
    require!(
        clock.unix_timestamp >= timelock.execute_after,
        MyError::TimelockNotExpired
    );
    // Execute the action...
    Ok(())
}""",
     "Queue sensitive operations with a delay. Users can review pending actions before execution."),
    ("multisig threshold", "require multiple signers to approve an action",
     """#[account]
#[derive(InitSpace)]
pub struct Multisig {
    pub signers: [Pubkey; 3],
    pub threshold: u8,
    pub bump: u8,
}

pub fn execute_multisig(ctx: Context<ExecuteMultisig>) -> Result<()> {
    let multisig = &ctx.accounts.multisig;
    let mut approval_count: u8 = 0;

    for signer_info in ctx.remaining_accounts.iter() {
        if signer_info.is_signer {
            let is_member = multisig.signers.iter().any(|s| s == signer_info.key);
            if is_member {
                approval_count += 1;
            }
        }
    }

    require!(
        approval_count >= multisig.threshold,
        MyError::InsufficientSigners
    );
    Ok(())
}""",
     "Use `remaining_accounts` for variable-length signer lists. Check each against the stored signer set."),
]

for pattern, desc, code, explanation in ACCESS_PATTERNS:
    q = f"How do I {desc} in Anchor?"
    a = f"""```rust
use anchor_lang::prelude::*;

{code}
```

{explanation}"""

    PAIRS.append(("access-control", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 14: State machines
# ═══════════════════════════════════════════════════════════════════════════════

STATE_MACHINES = [
    ("order", ["Created", "Funded", "Matched", "Settled", "Cancelled"],
     [("Created", "Funded", "fund_order"), ("Funded", "Matched", "match_order"),
      ("Matched", "Settled", "settle_order"), ("Created", "Cancelled", "cancel_order"),
      ("Funded", "Cancelled", "cancel_order")]),
    ("loan", ["Requested", "Approved", "Active", "Repaid", "Defaulted", "Liquidated"],
     [("Requested", "Approved", "approve_loan"), ("Approved", "Active", "disburse_loan"),
      ("Active", "Repaid", "repay_loan"), ("Active", "Defaulted", "mark_default"),
      ("Defaulted", "Liquidated", "liquidate")]),
    ("auction", ["Pending", "Active", "Ended", "Settled", "Cancelled"],
     [("Pending", "Active", "start_auction"), ("Active", "Ended", "end_auction"),
      ("Ended", "Settled", "settle_auction"), ("Pending", "Cancelled", "cancel_auction")]),
    ("campaign", ["Draft", "Active", "Paused", "Completed", "Refunding"],
     [("Draft", "Active", "launch_campaign"), ("Active", "Paused", "pause_campaign"),
      ("Paused", "Active", "resume_campaign"), ("Active", "Completed", "complete_campaign"),
      ("Active", "Refunding", "start_refund")]),
]

for entity, states, transitions in STATE_MACHINES:
    sn = struct_name(entity)
    states_code = "\n".join(f"    {s}," for s in states)
    match_arms = "\n".join(
        f'            ({sn}State::{frm}, {sn}State::{to}) => Ok(()),'
        for frm, to, _ in transitions
    )
    transition_fns = "\n\n".join(f"""    pub fn {fn_name}(ctx: Context<Transition{sn}>) -> Result<()> {{
        let account = &mut ctx.accounts.{entity};
        account.transition({sn}State::{to})?;
        Ok(())
    }}""" for frm, to, fn_name in transitions)

    q = f"How do I implement a state machine for a {entity} in Anchor with states: {', '.join(states)}?"
    a = f"""Use an enum for states and validate transitions:

```rust
use anchor_lang::prelude::*;

#[derive(AnchorSerialize, AnchorDeserialize, Clone, PartialEq, Eq, InitSpace)]
pub enum {sn}State {{
{states_code}
}}

#[account]
#[derive(InitSpace)]
pub struct {sn} {{
    pub authority: Pubkey,
    pub state: {sn}State,
    pub bump: u8,
}}

impl {sn} {{
    pub fn transition(&mut self, new_state: {sn}State) -> Result<()> {{
        let valid = match (&self.state, &new_state) {{
{match_arms}
            _ => Err(error!(MyError::InvalidTransition)),
        }};
        valid?;
        self.state = new_state;
        Ok(())
    }}
}}

#[program]
pub mod {entity}_program {{
    use super::*;

{transition_fns}
}}
```

The state machine pattern:
1. Define all states as an enum (derives `AnchorSerialize`/`AnchorDeserialize`)
2. Define valid transitions in a match expression
3. Invalid transitions return an error
4. Each instruction handler calls `transition()` to move between states"""

    PAIRS.append(("state-machine", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 15: Init mint + metadata
# ═══════════════════════════════════════════════════════════════════════════════

MINT_CONFIGS = [
    (6, True, "fungible token with 6 decimals and freeze authority"),
    (9, True, "fungible token with 9 decimals (like SOL) and freeze authority"),
    (0, False, "NFT (0 decimals, no freeze authority)"),
    (2, False, "semi-fungible token with 2 decimals"),
]

for decimals, freeze, desc in MINT_CONFIGS:
    freeze_code = "Some(&ctx.accounts.authority.key())" if freeze else "None"
    q = f"How do I create a {desc} mint in Anchor?"
    a = f"""```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{{self, Mint, Token, InitializeMint}};

#[derive(Accounts)]
pub struct CreateMint<'info> {{
    #[account(
        init,
        payer = authority,
        mint::decimals = {decimals},
        mint::authority = authority,{"" if not freeze else f"""
        mint::freeze_authority = authority,"""}
    )]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}}
```

- `decimals = {decimals}`: {"Standard for USD-pegged tokens (USDC uses 6)" if decimals == 6 else "Matches SOL's precision" if decimals == 9 else "NFTs have 0 decimals with supply of 1" if decimals == 0 else "Useful for tokens representing cents or partial units"}
- `mint::authority`: Who can mint new tokens
- {"`mint::freeze_authority`: Who can freeze token accounts (useful for regulated tokens)" if freeze else "No freeze authority — token accounts can never be frozen"}
- Anchor handles the `create_account` + `initialize_mint` CPIs automatically"""

    PAIRS.append(("mint-init", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 16: Zero-copy accounts
# ═══════════════════════════════════════════════════════════════════════════════

ZERO_COPY = [
    ("order_book", "an order book with large arrays",
     """#[account(zero_copy)]
#[repr(C)]
pub struct OrderBook {
    pub authority: Pubkey,
    pub bids: [Order; 256],
    pub asks: [Order; 256],
    pub bid_count: u32,
    pub ask_count: u32,
    pub sequence_number: u64,
}

#[zero_copy]
#[repr(C)]
pub struct Order {
    pub owner: Pubkey,
    pub price: u64,
    pub quantity: u64,
    pub timestamp: i64,
}""",
     "256 orders per side × ~56 bytes each = ~28KB. Without zero_copy this would require deserializing all 28KB on every instruction."),
    ("leaderboard", "a leaderboard with many entries",
     """#[account(zero_copy)]
#[repr(C)]
pub struct Leaderboard {
    pub authority: Pubkey,
    pub entries: [LeaderboardEntry; 1000],
    pub count: u32,
    pub last_updated: i64,
}

#[zero_copy]
#[repr(C)]
pub struct LeaderboardEntry {
    pub player: Pubkey,
    pub score: u64,
}""",
     "1000 entries × 40 bytes = 40KB. Zero-copy avoids deserializing the entire array when only updating one entry."),
    ("amm_pool", "an AMM pool with price history",
     """#[account(zero_copy)]
#[repr(C)]
pub struct AmmPool {
    pub authority: Pubkey,
    pub token_a_mint: Pubkey,
    pub token_b_mint: Pubkey,
    pub reserve_a: u64,
    pub reserve_b: u64,
    pub lp_supply: u64,
    pub fee_bps: u16,
    pub price_history: [PricePoint; 512],
    pub history_index: u16,
}

#[zero_copy]
#[repr(C)]
pub struct PricePoint {
    pub price: u64,
    pub timestamp: i64,
}""",
     "512 price points as a circular buffer. Access individual prices without loading the full history."),
]

for name, desc, code, explanation in ZERO_COPY:
    q = f"When should I use zero-copy accounts in Anchor? Show me an example for {desc}."
    a = f"""Use `#[account(zero_copy)]` for accounts larger than ~1KB that don't need full deserialization:

```rust
use anchor_lang::prelude::*;

{code}
```

{explanation}

Usage in account validation:

```rust
#[derive(Accounts)]
pub struct Update<'info> {{
    #[account(mut)]
    pub data: AccountLoader<'info, {struct_name(name)}>,
    pub authority: Signer<'info>,
}}

pub fn update(ctx: Context<Update>) -> Result<()> {{
    let mut data = ctx.accounts.data.load_mut()?;
    // Access fields directly — no full deserialization
    data.last_updated = Clock::get()?.unix_timestamp;
    Ok(())
}}
```

Key rules:
- Use `AccountLoader` instead of `Account` in account structs
- Call `.load()` for read-only, `.load_mut()` for mutable access
- All types must be `#[repr(C)]` for stable memory layout
- Inner types use `#[zero_copy]` instead of `#[account]`
- Max account size: 10MB (but practical limit is ~10KB per CU budget)"""

    PAIRS.append(("zero-copy", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 17: System program operations
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_OPS = [
    ("transfer SOL between accounts",
     """pub fn transfer_sol(ctx: Context<TransferSol>, amount: u64) -> Result<()> {
    let ix = anchor_lang::solana_program::system_instruction::transfer(
        &ctx.accounts.from.key(),
        &ctx.accounts.to.key(),
        amount,
    );
    anchor_lang::solana_program::program::invoke(
        &ix,
        &[
            ctx.accounts.from.to_account_info(),
            ctx.accounts.to.to_account_info(),
        ],
    )?;
    Ok(())
}

#[derive(Accounts)]
pub struct TransferSol<'info> {
    #[account(mut)]
    pub from: Signer<'info>,
    #[account(mut)]
    /// CHECK: receiving SOL
    pub to: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}"""),
    ("transfer SOL from a PDA",
     """pub fn pda_transfer_sol(ctx: Context<PdaTransferSol>, amount: u64) -> Result<()> {
    let vault = &ctx.accounts.vault;
    let vault_lamports = vault.to_account_info().lamports();
    require!(vault_lamports >= amount, MyError::InsufficientFunds);

    **vault.to_account_info().try_borrow_mut_lamports()? -= amount;
    **ctx.accounts.recipient.to_account_info().try_borrow_mut_lamports()? += amount;
    Ok(())
}"""),
    ("allocate space for an account",
     """pub fn allocate_account(ctx: Context<AllocateAccount>, space: u64) -> Result<()> {
    let rent = Rent::get()?;
    let lamports = rent.minimum_balance(space as usize);

    let ix = anchor_lang::solana_program::system_instruction::create_account(
        &ctx.accounts.payer.key(),
        &ctx.accounts.new_account.key(),
        lamports,
        space,
        &ctx.accounts.owner_program.key(),
    );
    anchor_lang::solana_program::program::invoke(
        &ix,
        &[
            ctx.accounts.payer.to_account_info(),
            ctx.accounts.new_account.to_account_info(),
        ],
    )?;
    Ok(())
}"""),
]

for desc, code in SYSTEM_OPS:
    q = f"How do I {desc} in a Solana/Anchor program?"
    a = f"""```rust
use anchor_lang::prelude::*;

#[program]
pub mod system_ops {{
    use super::*;

    {code}
}}
```

For PDA-to-account SOL transfers, you can directly modify lamport balances (no CPI needed) since the program owns the PDA. For wallet-to-wallet transfers, use the system program `transfer` instruction via CPI."""

    PAIRS.append(("system-ops", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Template 18: Common Anchor patterns / idioms
# ═══════════════════════════════════════════════════════════════════════════════

IDIOMS = [
    ("store and verify a bump seed",
     """// In init instruction:
pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
    let account = &mut ctx.accounts.my_account;
    account.bump = ctx.bumps.my_account; // Store the bump
    Ok(())
}

// In subsequent instructions — verify with stored bump:
#[derive(Accounts)]
pub struct UseAccount<'info> {
    #[account(
        seeds = [b"my-seed", authority.key().as_ref()],
        bump = my_account.bump, // Use stored bump (saves compute)
    )]
    pub my_account: Account<'info, MyAccount>,
    pub authority: Signer<'info>,
}""",
     "Storing the bump avoids re-deriving it on every instruction, saving ~4,500 compute units."),
    ("use remaining_accounts for variable-length inputs",
     """pub fn process_batch(ctx: Context<ProcessBatch>) -> Result<()> {
    for account_info in ctx.remaining_accounts.iter() {
        // Deserialize and validate each account
        let account: Account<MyAccount> = Account::try_from(account_info)?;
        require!(account.authority == ctx.accounts.authority.key(), MyError::Unauthorized);
        // Process...
    }
    Ok(())
}""",
     "`remaining_accounts` allows passing a variable number of accounts. Always validate each one."),
    ("use Box for large accounts in the stack",
     """#[derive(Accounts)]
pub struct LargeAccounts<'info> {
    #[account(mut)]
    pub big_data: Box<Account<'info, LargeStruct>>,
    #[account(mut)]
    pub another_big: Box<Account<'info, AnotherLarge>>,
    pub authority: Signer<'info>,
}""",
     "Anchor account structs live on the stack. If your instruction has many large accounts, wrap them in `Box<>` to move them to the heap and avoid stack overflow."),
    ("use #[instruction] to access instruction args in constraints",
     """#[derive(Accounts)]
#[instruction(amount: u64, recipient: Pubkey)]
pub struct Transfer<'info> {
    #[account(
        mut,
        constraint = vault.amount >= amount @ MyError::InsufficientFunds,
    )]
    pub vault: Account<'info, Vault>,
    #[account(
        mut,
        constraint = destination.owner == recipient @ MyError::WrongRecipient,
    )]
    pub destination: Account<'info, TokenAccount>,
}""",
     "The `#[instruction()]` attribute makes instruction parameters available in account constraints. Parameters must match the instruction signature order."),
]

for desc, code, explanation in IDIOMS:
    q = f"What's the best way to {desc} in Anchor?"
    a = f"""```rust
use anchor_lang::prelude::*;

{code}
```

{explanation}"""

    PAIRS.append(("idioms", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Write output
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = [rec(content, category=cat) for cat, content in PAIRS]
    out_path = OUT_DIR / "synthetic-bulk1.jsonl"
    count = write_jsonl(records, out_path)
    print(f"Generated {count} records → {out_path}")


if __name__ == "__main__":
    main()
