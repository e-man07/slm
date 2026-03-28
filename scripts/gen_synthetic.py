#!/usr/bin/env python3
"""Generate all synthetic training data directly (no external API needed).

Produces OSS-Instruct, Evol-Instruct, and GLAN data as JSONL.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schema import Record, write_jsonl

SYSTEM = "You are an expert Solana and Anchor developer. Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns."
OUT_DIR = Path(__file__).parent.parent / "data" / "processed"


def m(user: str, assistant: str) -> str:
    """Create ChatML messages JSON string."""
    return json.dumps([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ], ensure_ascii=False)


def rec(content: str, method: str, category: str = "") -> Record:
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
# GLAN: Taxonomy-based generation across all Solana dev topics
# ═══════════════════════════════════════════════════════════════════════════════

GLAN = []

# ── PDA Derivation ──────────────────────────────────────────────────────────

GLAN.append(("pda", m(
    "How do I derive a PDA in Anchor using a user's public key as a seed?",
    """In Anchor, you derive PDAs using the `seeds` and `bump` constraints in your account struct:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod pda_example {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let user_account = &mut ctx.accounts.user_account;
        user_account.authority = ctx.accounts.user.key();
        user_account.bump = ctx.bumps.user_account;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(
        init,
        payer = user,
        space = 8 + UserAccount::INIT_SPACE,
        seeds = [b"user-account", user.key().as_ref()],
        bump,
    )]
    pub user_account: Account<'info, UserAccount>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct UserAccount {
    pub authority: Pubkey,
    pub bump: u8,
}
```

Key points:
- `seeds` defines the PDA derivation inputs — here `b"user-account"` (a static string) and the user's pubkey
- `bump` tells Anchor to find and verify the canonical bump seed automatically
- Store the bump in your account (`ctx.bumps.user_account`) so you can use it later for CPI signing
- `InitSpace` derive macro calculates space automatically — just add `8 +` for the discriminator"""
)))

GLAN.append(("pda", m(
    "How do I create a PDA with multiple seeds including a u64 identifier?",
    """Use multiple seeds by combining byte slices in the `seeds` constraint:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod multi_seed_pda {
    use super::*;

    pub fn create_order(ctx: Context<CreateOrder>, order_id: u64) -> Result<()> {
        let order = &mut ctx.accounts.order;
        order.maker = ctx.accounts.maker.key();
        order.order_id = order_id;
        order.bump = ctx.bumps.order;
        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(order_id: u64)]
pub struct CreateOrder<'info> {
    #[account(mut)]
    pub maker: Signer<'info>,
    #[account(
        init,
        payer = maker,
        space = 8 + Order::INIT_SPACE,
        seeds = [b"order", maker.key().as_ref(), &order_id.to_le_bytes()],
        bump,
    )]
    pub order: Account<'info, Order>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct Order {
    pub maker: Pubkey,
    pub order_id: u64,
    pub bump: u8,
}
```

The `#[instruction(order_id: u64)]` attribute lets you use instruction arguments in seeds. Convert `u64` to bytes with `to_le_bytes()`."""
)))

GLAN.append(("pda", m(
    "How do I use a PDA as a signer for CPI calls?",
    """When a PDA needs to sign a CPI (e.g., transferring tokens from a vault), pass the seeds via `CpiContext::new_with_signer`:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod vault_program {
    use super::*;

    pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
        let seeds = &[
            b"vault".as_ref(),
            ctx.accounts.vault_state.authority.as_ref(),
            &[ctx.accounts.vault_state.bump],
        ];
        let signer_seeds = &[&seeds[..]];

        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.vault_token.to_account_info(),
                to: ctx.accounts.user_token.to_account_info(),
                authority: ctx.accounts.vault_state.to_account_info(),
            },
            signer_seeds,
        );
        token::transfer(cpi_ctx, amount)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(
        constraint = authority.key() == vault_state.authority @ ErrorCode::Unauthorized
    )]
    pub authority: Signer<'info>,
    #[account(
        seeds = [b"vault", authority.key().as_ref()],
        bump = vault_state.bump,
    )]
    pub vault_state: Account<'info, VaultState>,
    #[account(
        mut,
        token::mint = vault_token.mint,
        token::authority = vault_state,
    )]
    pub vault_token: Account<'info, TokenAccount>,
    #[account(mut)]
    pub user_token: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[account]
#[derive(InitSpace)]
pub struct VaultState {
    pub authority: Pubkey,
    pub bump: u8,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Unauthorized")]
    Unauthorized,
}
```

The PDA signs the CPI because you provide `signer_seeds` — Solana runtime verifies the seeds derive this PDA."""
)))

# ── Anchor Constraints ──────────────────────────────────────────────────────

GLAN.append(("constraints", m(
    "What are the most common Anchor account constraints and when do I use each?",
    """Here's a reference of the most-used Anchor constraints:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token, TokenAccount};

#[derive(Accounts)]
pub struct ExampleAccounts<'info> {
    // mut: account is writable (will be modified)
    #[account(mut)]
    pub payer: Signer<'info>,

    // init: create new account, must specify payer and space
    #[account(
        init,
        payer = payer,
        space = 8 + MyData::INIT_SPACE,
    )]
    pub new_account: Account<'info, MyData>,

    // init_if_needed: create only if it doesn't exist yet
    // (requires "init-if-needed" feature in Cargo.toml)
    #[account(
        init_if_needed,
        payer = payer,
        space = 8 + MyData::INIT_SPACE,
        seeds = [b"config"],
        bump,
    )]
    pub config: Account<'info, MyData>,

    // has_one: verify field matches another account
    #[account(
        mut,
        has_one = authority,
    )]
    pub owned_account: Account<'info, OwnedData>,
    pub authority: Signer<'info>,

    // close: close account, send rent to target
    #[account(
        mut,
        close = payer,
        has_one = authority,
    )]
    pub closing_account: Account<'info, OwnedData>,

    // constraint: arbitrary boolean check with custom error
    #[account(
        constraint = token_account.amount >= 100 @ MyError::InsufficientBalance
    )]
    pub token_account: Account<'info, TokenAccount>,

    // Token constraints: verify mint and authority
    #[account(
        token::mint = mint,
        token::authority = payer,
    )]
    pub user_tokens: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,

    // realloc: resize an existing account
    #[account(
        mut,
        realloc = 8 + MyData::INIT_SPACE,
        realloc::payer = payer,
        realloc::zero = false,
    )]
    pub resizable: Account<'info, MyData>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}
```

Rules of thumb:
- Always use `has_one` or `constraint` for ownership checks — never do manual `if` checks in the instruction body
- `init` requires `system_program` in the accounts struct
- `close` sends all lamports to the specified account and zeros the data
- Token constraints (`token::mint`, `token::authority`) replace manual deserialization checks"""
)))

GLAN.append(("constraints", m(
    "How do I use the realloc constraint to resize an account dynamically?",
    """Use `realloc` when your account stores variable-length data (like a Vec or String) that may grow:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod dynamic_account {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let profile = &mut ctx.accounts.profile;
        profile.authority = ctx.accounts.user.key();
        profile.items = vec![];
        Ok(())
    }

    pub fn add_item(ctx: Context<AddItem>, item: String) -> Result<()> {
        require!(item.len() <= 64, ErrorCode::ItemTooLong);
        let profile = &mut ctx.accounts.profile;
        profile.items.push(item);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(
        init,
        payer = user,
        // Start with space for 0 items
        space = 8 + 32 + 4, // discriminator + pubkey + vec length
    )]
    pub profile: Account<'info, Profile>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(item: String)]
pub struct AddItem<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(
        mut,
        has_one = authority @ ErrorCode::Unauthorized,
        // Realloc to fit the new item (4 bytes length prefix + string bytes)
        realloc = 8 + 32 + 4 + profile.items.iter().map(|i| 4 + i.len()).sum::<usize>() + 4 + item.len(),
        realloc::payer = user,
        realloc::zero = false,
    )]
    pub profile: Account<'info, Profile>,
    #[account(constraint = user.key() == profile.authority)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct Profile {
    pub authority: Pubkey,
    pub items: Vec<String>,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Unauthorized")]
    Unauthorized,
    #[msg("Item exceeds max length of 64 characters")]
    ItemTooLong,
}
```

Key notes:
- `realloc::payer` pays if the account grows (gets refunded if it shrinks)
- `realloc::zero = false` means new bytes aren't zeroed (set to `true` for security-sensitive data)
- The `system_program` is required for realloc"""
)))

# ── SPL Token Operations ────────────────────────────────────────────────────

GLAN.append(("spl-tokens", m(
    "How do I create a token mint and mint tokens in Anchor?",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, MintTo, Token, TokenAccount};
use anchor_spl::associated_token::AssociatedToken;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod token_factory {
    use super::*;

    pub fn create_mint(ctx: Context<CreateMint>, decimals: u8) -> Result<()> {
        // Mint is initialized by Anchor via the init constraint
        msg!("Mint created: {}", ctx.accounts.mint.key());
        Ok(())
    }

    pub fn mint_tokens(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
        let cpi_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            MintTo {
                mint: ctx.accounts.mint.to_account_info(),
                to: ctx.accounts.token_account.to_account_info(),
                authority: ctx.accounts.authority.to_account_info(),
            },
        );
        token::mint_to(cpi_ctx, amount)?;
        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(decimals: u8)]
pub struct CreateMint<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        init,
        payer = authority,
        mint::decimals = decimals,
        mint::authority = authority.key(),
        mint::freeze_authority = authority.key(),
    )]
    pub mint: Account<'info, Mint>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct MintTokens<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        mut,
        mint::authority = authority.key(),
    )]
    pub mint: Account<'info, Mint>,
    #[account(
        init_if_needed,
        payer = authority,
        associated_token::mint = mint,
        associated_token::authority = authority,
    )]
    pub token_account: Account<'info, TokenAccount>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
}
```

The `mint::decimals`, `mint::authority` constraints handle all initialization. `associated_token::mint` and `associated_token::authority` create the ATA automatically."""
)))

GLAN.append(("spl-tokens", m(
    "How do I transfer SPL tokens between accounts in Anchor?",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod token_transfer {
    use super::*;

    pub fn transfer(ctx: Context<TransferTokens>, amount: u64) -> Result<()> {
        require!(amount > 0, ErrorCode::ZeroAmount);

        let cpi_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.from.to_account_info(),
                to: ctx.accounts.to.to_account_info(),
                authority: ctx.accounts.authority.to_account_info(),
            },
        );
        token::transfer(cpi_ctx, amount)?;

        msg!("Transferred {} tokens", amount);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct TransferTokens<'info> {
    pub authority: Signer<'info>,
    #[account(
        mut,
        token::authority = authority,
    )]
    pub from: Account<'info, TokenAccount>,
    #[account(
        mut,
        token::mint = from.mint, // Ensure same mint
    )]
    pub to: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Transfer amount must be greater than zero")]
    ZeroAmount,
}
```

The `token::authority` constraint ensures only the token owner can transfer. `token::mint = from.mint` prevents sending to wrong token type."""
)))

# ── CPI ─────────────────────────────────────────────────────────────────────

GLAN.append(("cpi", m(
    "How do I make a CPI call from one Anchor program to another?",
    """To call Program B from Program A, use `CpiContext::new` with Program B's accounts:

```rust
// ── Program B (callee) ──
use anchor_lang::prelude::*;

declare_id!("BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBb");

#[program]
pub mod program_b {
    use super::*;

    pub fn increment(ctx: Context<Increment>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.count = counter.count.checked_add(1).ok_or(ErrorCode::Overflow)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Increment<'info> {
    #[account(mut)]
    pub counter: Account<'info, Counter>,
}

#[account]
#[derive(InitSpace)]
pub struct Counter {
    pub count: u64,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Counter overflow")]
    Overflow,
}

// ── Program A (caller) ──
use anchor_lang::prelude::*;

declare_id!("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAa");

#[program]
pub mod program_a {
    use super::*;

    pub fn call_increment(ctx: Context<CallIncrement>) -> Result<()> {
        let cpi_program = ctx.accounts.program_b.to_account_info();
        let cpi_accounts = program_b::cpi::accounts::Increment {
            counter: ctx.accounts.counter.to_account_info(),
        };
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        program_b::cpi::increment(cpi_ctx)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CallIncrement<'info> {
    #[account(mut)]
    pub counter: Account<'info, program_b::Counter>,
    pub program_b: Program<'info, program_b::program::ProgramB>,
}
```

Anchor auto-generates the `cpi` module for each program. Import the callee and use `program_b::cpi::accounts::*` and `program_b::cpi::instruction_name()`."""
)))

GLAN.append(("cpi", m(
    "How do I transfer SOL using CPI to the System Program?",
    """```rust
use anchor_lang::prelude::*;
use anchor_lang::system_program::{self, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod sol_transfer {
    use super::*;

    pub fn send_sol(ctx: Context<SendSol>, amount: u64) -> Result<()> {
        let cpi_ctx = CpiContext::new(
            ctx.accounts.system_program.to_account_info(),
            Transfer {
                from: ctx.accounts.sender.to_account_info(),
                to: ctx.accounts.receiver.to_account_info(),
            },
        );
        system_program::transfer(cpi_ctx, amount)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct SendSol<'info> {
    #[account(mut)]
    pub sender: Signer<'info>,
    /// CHECK: receiver can be any account
    #[account(mut)]
    pub receiver: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}
```

Use `anchor_lang::system_program::Transfer` (not `anchor_spl::token::Transfer`) for SOL transfers. The sender must be a `Signer`."""
)))

# ── Error Handling ──────────────────────────────────────────────────────────

GLAN.append(("errors", m(
    "How do I define and use custom errors in Anchor?",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod error_example {
    use super::*;

    pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
        let vault = &ctx.accounts.vault;

        // Method 1: require! macro
        require!(amount > 0, VaultError::ZeroAmount);

        // Method 2: require_keys_eq! for pubkey comparison
        require_keys_eq!(
            ctx.accounts.authority.key(),
            vault.authority,
            VaultError::Unauthorized
        );

        // Method 3: require_gt!, require_gte! for numeric checks
        require_gte!(vault.balance, amount, VaultError::InsufficientFunds);

        // Method 4: constraint in accounts struct (preferred for account validation)
        // See the Withdraw struct below

        let vault = &mut ctx.accounts.vault;
        vault.balance = vault.balance.checked_sub(amount)
            .ok_or(VaultError::MathOverflow)?;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(
        constraint = authority.key() == vault.authority @ VaultError::Unauthorized
    )]
    pub authority: Signer<'info>,
    #[account(mut)]
    pub vault: Account<'info, Vault>,
}

#[account]
#[derive(InitSpace)]
pub struct Vault {
    pub authority: Pubkey,
    pub balance: u64,
}

// Errors start at 6000 in the program's error space
#[error_code]
pub enum VaultError {
    #[msg("Unauthorized access")]
    Unauthorized,         // 6000
    #[msg("Insufficient funds in vault")]
    InsufficientFunds,    // 6001
    #[msg("Amount must be greater than zero")]
    ZeroAmount,           // 6002
    #[msg("Math overflow")]
    MathOverflow,         // 6003
}
```

Anchor custom errors start at code 6000. On the client, parse with: `const parsed = AnchorError.parse(error.logs)` to get the error name and code."""
)))

# ── DeFi Patterns ───────────────────────────────────────────────────────────

GLAN.append(("defi", m(
    "How do I build a simple token vault with deposit and withdraw in Anchor?",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};
use anchor_spl::associated_token::AssociatedToken;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod token_vault {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let vault = &mut ctx.accounts.vault_state;
        vault.authority = ctx.accounts.authority.key();
        vault.mint = ctx.accounts.mint.key();
        vault.total_deposited = 0;
        vault.bump = ctx.bumps.vault_state;
        Ok(())
    }

    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        require!(amount > 0, VaultError::ZeroAmount);

        // Transfer tokens from user to vault
        let cpi_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.user_token.to_account_info(),
                to: ctx.accounts.vault_token.to_account_info(),
                authority: ctx.accounts.user.to_account_info(),
            },
        );
        token::transfer(cpi_ctx, amount)?;

        let vault = &mut ctx.accounts.vault_state;
        vault.total_deposited = vault.total_deposited.checked_add(amount)
            .ok_or(VaultError::Overflow)?;
        Ok(())
    }

    pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
        require!(amount > 0, VaultError::ZeroAmount);

        let vault = &ctx.accounts.vault_state;
        let seeds = &[
            b"vault".as_ref(),
            vault.authority.as_ref(),
            &[vault.bump],
        ];

        // Transfer tokens from vault to user (PDA signs)
        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.vault_token.to_account_info(),
                to: ctx.accounts.user_token.to_account_info(),
                authority: ctx.accounts.vault_state.to_account_info(),
            },
            &[seeds],
        );
        token::transfer(cpi_ctx, amount)?;

        let vault = &mut ctx.accounts.vault_state;
        vault.total_deposited = vault.total_deposited.checked_sub(amount)
            .ok_or(VaultError::Overflow)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    pub mint: Account<'info, Mint>,
    #[account(
        init,
        payer = authority,
        space = 8 + VaultState::INIT_SPACE,
        seeds = [b"vault", authority.key().as_ref()],
        bump,
    )]
    pub vault_state: Account<'info, VaultState>,
    #[account(
        init,
        payer = authority,
        token::mint = mint,
        token::authority = vault_state,
    )]
    pub vault_token: Account<'info, TokenAccount>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Deposit<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(mut, seeds = [b"vault", vault_state.authority.as_ref()], bump = vault_state.bump)]
    pub vault_state: Account<'info, VaultState>,
    #[account(mut, token::mint = vault_state.mint, token::authority = vault_state)]
    pub vault_token: Account<'info, TokenAccount>,
    #[account(mut, token::mint = vault_state.mint, token::authority = user)]
    pub user_token: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(constraint = authority.key() == vault_state.authority @ VaultError::Unauthorized)]
    pub authority: Signer<'info>,
    #[account(mut, seeds = [b"vault", vault_state.authority.as_ref()], bump = vault_state.bump)]
    pub vault_state: Account<'info, VaultState>,
    #[account(mut, token::mint = vault_state.mint, token::authority = vault_state)]
    pub vault_token: Account<'info, TokenAccount>,
    #[account(mut, token::mint = vault_state.mint)]
    pub user_token: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[account]
#[derive(InitSpace)]
pub struct VaultState {
    pub authority: Pubkey,
    pub mint: Pubkey,
    pub total_deposited: u64,
    pub bump: u8,
}

#[error_code]
pub enum VaultError {
    #[msg("Unauthorized")] Unauthorized,
    #[msg("Amount must be > 0")] ZeroAmount,
    #[msg("Math overflow")] Overflow,
}
```"""
)))

GLAN.append(("defi", m(
    "How do I implement a simple staking program with reward distribution in Anchor?",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer, MintTo};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod staking {
    use super::*;

    pub fn initialize_pool(ctx: Context<InitializePool>, reward_rate: u64) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        pool.authority = ctx.accounts.authority.key();
        pool.stake_mint = ctx.accounts.stake_mint.key();
        pool.reward_rate = reward_rate; // tokens per second per staked token (scaled by 1e9)
        pool.last_update = Clock::get()?.unix_timestamp;
        pool.total_staked = 0;
        pool.reward_per_token_stored = 0;
        pool.bump = ctx.bumps.pool;
        Ok(())
    }

    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        require!(amount > 0, StakeError::ZeroAmount);

        // Update rewards before changing stake
        update_rewards(&mut ctx.accounts.pool, &mut ctx.accounts.user_stake)?;

        // Transfer tokens to pool vault
        let cpi_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.user_token.to_account_info(),
                to: ctx.accounts.pool_vault.to_account_info(),
                authority: ctx.accounts.user.to_account_info(),
            },
        );
        token::transfer(cpi_ctx, amount)?;

        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;
        pool.total_staked = pool.total_staked.checked_add(amount).ok_or(StakeError::Overflow)?;
        user_stake.staked_amount = user_stake.staked_amount.checked_add(amount).ok_or(StakeError::Overflow)?;

        Ok(())
    }

    pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
        update_rewards(&mut ctx.accounts.pool, &mut ctx.accounts.user_stake)?;

        let rewards = ctx.accounts.user_stake.pending_rewards;
        require!(rewards > 0, StakeError::NoRewards);

        ctx.accounts.user_stake.pending_rewards = 0;
        msg!("Claimed {} reward tokens", rewards);
        Ok(())
    }
}

fn update_rewards(pool: &mut Account<Pool>, user_stake: &mut Account<UserStake>) -> Result<()> {
    let now = Clock::get()?.unix_timestamp;
    if pool.total_staked > 0 {
        let time_elapsed = (now - pool.last_update) as u64;
        let reward_increment = time_elapsed
            .checked_mul(pool.reward_rate).ok_or(StakeError::Overflow)?
            .checked_div(pool.total_staked).ok_or(StakeError::Overflow)?;
        pool.reward_per_token_stored = pool.reward_per_token_stored
            .checked_add(reward_increment).ok_or(StakeError::Overflow)?;
    }
    pool.last_update = now;

    user_stake.pending_rewards = user_stake.pending_rewards
        .checked_add(
            user_stake.staked_amount
                .checked_mul(pool.reward_per_token_stored.checked_sub(user_stake.reward_per_token_paid).ok_or(StakeError::Overflow)?)
                .ok_or(StakeError::Overflow)?
                .checked_div(1_000_000_000) // scale factor
                .ok_or(StakeError::Overflow)?
        ).ok_or(StakeError::Overflow)?;
    user_stake.reward_per_token_paid = pool.reward_per_token_stored;

    Ok(())
}

#[account]
#[derive(InitSpace)]
pub struct Pool {
    pub authority: Pubkey,
    pub stake_mint: Pubkey,
    pub reward_rate: u64,
    pub last_update: i64,
    pub total_staked: u64,
    pub reward_per_token_stored: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct UserStake {
    pub owner: Pubkey,
    pub staked_amount: u64,
    pub reward_per_token_paid: u64,
    pub pending_rewards: u64,
}

#[error_code]
pub enum StakeError {
    #[msg("Amount must be > 0")] ZeroAmount,
    #[msg("No rewards to claim")] NoRewards,
    #[msg("Math overflow")] Overflow,
}

// Account structs for instructions omitted for brevity — follow the same
// pattern as the vault example with seeds, constraints, and token accounts.
```

This implements the standard "reward per token" algorithm used by Synthetix and most DeFi staking protocols."""
)))

# ── Security ────────────────────────────────────────────────────────────────

GLAN.append(("security", m(
    "What are the most important security checks in a Solana Anchor program?",
    """Key security patterns every Anchor program should follow:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{Token, TokenAccount, Mint};

// 1. ALWAYS use checked math — never raw arithmetic
pub fn safe_math_example(a: u64, b: u64) -> Result<u64> {
    a.checked_add(b).ok_or_else(|| error!(SecurityError::MathOverflow))
}

// 2. Use Anchor constraints for ALL validation
#[derive(Accounts)]
pub struct SecureAccounts<'info> {
    // ✅ Signer check — verifies this account signed the transaction
    pub authority: Signer<'info>,

    // ✅ Ownership check — has_one verifies vault.authority == authority.key()
    #[account(
        mut,
        has_one = authority @ SecurityError::Unauthorized,
    )]
    pub vault: Account<'info, Vault>,

    // ✅ Mint check — ensures token account matches expected mint
    #[account(
        token::mint = expected_mint,
        token::authority = authority,
    )]
    pub user_tokens: Account<'info, TokenAccount>,
    pub expected_mint: Account<'info, Mint>,

    // ✅ PDA validation — seeds + bump verify the account is the correct PDA
    #[account(
        seeds = [b"config", authority.key().as_ref()],
        bump = config.bump,
    )]
    pub config: Account<'info, Config>,

    // ✅ Program check — verifies the program ID
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

// 3. Use #[account] discriminators (automatic in Anchor)
// The 8-byte discriminator prevents account type confusion attacks

// 4. Close accounts properly with the close constraint
#[derive(Accounts)]
pub struct CloseAccount<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        mut,
        close = authority,           // ✅ Sends rent to authority
        has_one = authority,          // ✅ Only owner can close
    )]
    pub account: Account<'info, Vault>,
}

// 5. Define clear error types
#[error_code]
pub enum SecurityError {
    #[msg("Unauthorized access")] Unauthorized,
    #[msg("Math overflow")] MathOverflow,
    #[msg("Invalid account state")] InvalidState,
}

#[account]
#[derive(InitSpace)]
pub struct Vault { pub authority: Pubkey, pub balance: u64 }

#[account]
#[derive(InitSpace)]
pub struct Config { pub bump: u8 }
```

Common mistakes to avoid:
- Never use `AccountInfo` (unchecked) when a typed `Account<>` works
- Never do arithmetic without `checked_*` methods
- Never skip `has_one` or `constraint` checks for ownership
- Never forget to verify PDA bumps match stored bumps"""
)))

GLAN.append(("security", m(
    "How do I safely close an account and prevent closed-account attacks in Anchor?",
    """Anchor's `close` constraint handles this correctly:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod safe_close {
    use super::*;

    pub fn close_listing(ctx: Context<CloseListing>) -> Result<()> {
        // Any cleanup logic before closing
        msg!("Closing listing: {}", ctx.accounts.listing.key());
        // The close constraint handles:
        // 1. Transferring all lamports to the recipient
        // 2. Zeroing the account data
        // 3. Setting the owner to the System Program
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CloseListing<'info> {
    #[account(mut)]
    pub seller: Signer<'info>,
    #[account(
        mut,
        close = seller,                                    // Send rent to seller
        has_one = seller @ CloseError::NotSeller,          // Only seller can close
        constraint = !listing.is_active @ CloseError::StillActive, // Must deactivate first
    )]
    pub listing: Account<'info, Listing>,
}

#[account]
#[derive(InitSpace)]
pub struct Listing {
    pub seller: Pubkey,
    pub price: u64,
    pub is_active: bool,
}

#[error_code]
pub enum CloseError {
    #[msg("Only the seller can close this listing")]
    NotSeller,
    #[msg("Deactivate the listing before closing")]
    StillActive,
}
```

Anchor's `close` constraint is safe against the old "closed account discriminator" issue — the account data is zeroed and ownership transferred to System Program, preventing reuse. This was fixed in Anchor years ago and is not a concern with modern Anchor."""
)))

# ── TypeScript Client ───────────────────────────────────────────────────────

GLAN.append(("typescript", m(
    "How do I build and send a transaction using @solana/web3.js with an Anchor program?",
    """```typescript
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { PublicKey, SystemProgram } from "@solana/web3.js";
import { MyProgram } from "../target/types/my_program";

async function main() {
  // Setup provider (reads from ANCHOR_PROVIDER_URL and ANCHOR_WALLET)
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.MyProgram as Program<MyProgram>;
  const user = provider.wallet.publicKey;

  // Derive PDA
  const [userAccount] = PublicKey.findProgramAddressSync(
    [Buffer.from("user-account"), user.toBuffer()],
    program.programId
  );

  // Send transaction
  try {
    const tx = await program.methods
      .initialize()
      .accountsStrict({
        user: user,
        userAccount: userAccount,
        systemProgram: SystemProgram.programId,
      })
      .rpc();

    console.log("Transaction signature:", tx);

    // Wait for confirmation
    const confirmation = await provider.connection.confirmTransaction(tx, "confirmed");
    console.log("Confirmed in slot:", confirmation.value.context.slot);

    // Fetch the account data
    const account = await program.account.userAccount.fetch(userAccount);
    console.log("Authority:", account.authority.toBase58());
    console.log("Bump:", account.bump);
  } catch (err) {
    if (err instanceof anchor.AnchorError) {
      console.error("Program error:", err.error.errorMessage);
      console.error("Error code:", err.error.errorCode.number);
    } else {
      throw err;
    }
  }
}

main();
```

Key patterns:
- Use `program.methods.instructionName()` for the fluent builder API
- `accountsStrict()` requires all accounts (safer than `accounts()` which allows omissions)
- `PublicKey.findProgramAddressSync` derives PDAs client-side
- Handle `AnchorError` for typed error responses"""
)))

GLAN.append(("typescript", m(
    "How do I fetch and decode Anchor account data in TypeScript?",
    """```typescript
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { PublicKey, Connection } from "@solana/web3.js";
import { MyProgram } from "../target/types/my_program";

const connection = new Connection("https://api.mainnet-beta.solana.com");

// Method 1: Fetch a single account by address
async function fetchSingleAccount(program: Program<MyProgram>, address: PublicKey) {
  const account = await program.account.vault.fetch(address);
  console.log("Authority:", account.authority.toBase58());
  console.log("Balance:", account.balance.toNumber());
}

// Method 2: Fetch all accounts of a type
async function fetchAllVaults(program: Program<MyProgram>) {
  const vaults = await program.account.vault.all();
  for (const v of vaults) {
    console.log(`Vault ${v.publicKey}: balance=${v.account.balance}`);
  }
}

// Method 3: Fetch with filters (memcmp on account fields)
async function fetchVaultsByAuthority(
  program: Program<MyProgram>,
  authority: PublicKey
) {
  const vaults = await program.account.vault.all([
    {
      memcmp: {
        offset: 8, // Skip 8-byte discriminator
        bytes: authority.toBase58(),
      },
    },
  ]);
  return vaults;
}

// Method 4: Subscribe to account changes
function watchAccount(program: Program<MyProgram>, address: PublicKey) {
  const listener = program.account.vault.subscribe(address, "confirmed");
  // Note: subscribe returns an EventEmitter in older versions,
  // or use connection.onAccountChange for raw subscriptions
  return listener;
}

// Method 5: Fetch account with error handling for non-existent accounts
async function safeFetch(program: Program<MyProgram>, address: PublicKey) {
  const account = await program.account.vault.fetchNullable(address);
  if (account === null) {
    console.log("Account does not exist");
    return null;
  }
  return account;
}
```

Key tips:
- `fetch()` throws if account doesn't exist — use `fetchNullable()` for optional accounts
- `all()` fetches every account of that type (can be expensive on mainnet)
- `memcmp` filters run on-chain so only matching accounts are returned
- The 8-byte discriminator is Anchor's account type identifier — offset account fields by 8"""
)))

# ── Testing ─────────────────────────────────────────────────────────────────

GLAN.append(("testing", m(
    "How do I write tests for an Anchor program using Bankrun?",
    """```typescript
import { describe, it } from "node:test";
import assert from "node:assert";
import { startAnchor } from "solana-bankrun";
import { BankrunProvider } from "anchor-bankrun";
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { PublicKey, Keypair, SystemProgram } from "@solana/web3.js";
import { Counter } from "../target/types/counter";

describe("Counter Program", () => {
  let provider: BankrunProvider;
  let program: Program<Counter>;
  let counterPda: PublicKey;

  it("initializes the counter", async () => {
    // Start local validator with program deployed
    const context = await startAnchor(".", [], []);
    provider = new BankrunProvider(context);
    anchor.setProvider(provider);
    program = anchor.workspace.Counter as Program<Counter>;

    const user = provider.wallet.publicKey;
    [counterPda] = PublicKey.findProgramAddressSync(
      [Buffer.from("counter"), user.toBuffer()],
      program.programId
    );

    await program.methods
      .initialize()
      .accountsStrict({
        user,
        counter: counterPda,
        systemProgram: SystemProgram.programId,
      })
      .rpc();

    const account = await program.account.counter.fetch(counterPda);
    assert.equal(account.count.toNumber(), 0);
  });

  it("increments the counter", async () => {
    await program.methods
      .increment()
      .accountsStrict({ counter: counterPda })
      .rpc();

    const account = await program.account.counter.fetch(counterPda);
    assert.equal(account.count.toNumber(), 1);
  });

  it("fails with unauthorized user", async () => {
    const attacker = Keypair.generate();

    try {
      await program.methods
        .adminReset()
        .accountsStrict({
          authority: attacker.publicKey,
          counter: counterPda,
        })
        .signers([attacker])
        .rpc();
      assert.fail("Should have thrown");
    } catch (err) {
      assert.ok(err instanceof anchor.AnchorError);
      assert.equal(err.error.errorCode.code, "Unauthorized");
    }
  });
});
```

Bankrun is faster than `anchor test` because it runs an in-process validator without needing `solana-test-validator`. Install: `npm install solana-bankrun anchor-bankrun`."""
)))

# ── Account State & Serialization ──────────────────────────────────────────

GLAN.append(("accounts", m(
    "How do I define account structs with proper space allocation in Anchor?",
    """In Anchor 0.30+, use the `#[account]` attribute and implement `space` via `INIT_SPACE`:

```rust
use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct GameState {
    pub authority: Pubkey,            // 32 bytes
    pub score: u64,                   // 8 bytes
    pub level: u8,                    // 1 byte
    pub is_active: bool,              // 1 byte
    #[max_len(32)]
    pub player_name: String,          // 4 + 32 bytes
    #[max_len(10)]
    pub inventory: Vec<u64>,          // 4 + (10 * 8) bytes
    pub last_played: i64,             // 8 bytes
    pub bump: u8,                     // 1 byte
}
```

Use `#[derive(InitSpace)]` with `#[max_len(...)]` for dynamic types. In `init`:

```rust
#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = player,
        space = 8 + GameState::INIT_SPACE,
        seeds = [b"game", player.key().as_ref()],
        bump,
    )]
    pub game_state: Account<'info, GameState>,
    #[account(mut)]
    pub player: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

The `8 +` prefix accounts for Anchor's 8-byte discriminator. `InitSpace` calculates the rest automatically."""
)))

GLAN.append(("accounts", m(
    "How do I use zero-copy accounts for large data in Anchor?",
    """For accounts larger than 10KB, use zero-copy deserialization:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[account(zero_copy)]
#[repr(C)]
pub struct LargeState {
    pub authority: Pubkey,
    pub data: [u64; 1024],
    pub count: u64,
    pub bump: u8,
}

#[program]
pub mod large_account {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let state = &mut ctx.accounts.state.load_init()?;
        state.authority = ctx.accounts.authority.key();
        state.count = 0;
        state.bump = ctx.bumps.state;
        Ok(())
    }

    pub fn update(ctx: Context<Update>, index: u64, value: u64) -> Result<()> {
        let state = &mut ctx.accounts.state.load_mut()?;
        require!(index < 1024, ErrorCode::InvalidIndex);
        state.data[index as usize] = value;
        state.count += 1;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init, payer = authority,
        space = 8 + std::mem::size_of::<LargeState>(),
        seeds = [b"large"], bump,
    )]
    pub state: AccountLoader<'info, LargeState>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

Use `AccountLoader` instead of `Account`, call `.load_init()?`/`.load_mut()?`/`.load()?`, add `#[repr(C)]`, and avoid `Vec`/`String` (use fixed arrays)."""
)))

GLAN.append(("accounts", m(
    "How do I close an account and reclaim rent in Anchor?",
    """Use the `close` constraint:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod closeable {
    use super::*;

    pub fn close_account(_ctx: Context<CloseAccount>) -> Result<()> {
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CloseAccount<'info> {
    #[account(
        mut,
        close = authority,
        has_one = authority,
        seeds = [b"data", authority.key().as_ref()],
        bump = data_account.bump,
    )]
    pub data_account: Account<'info, DataAccount>,
    #[account(mut)]
    pub authority: Signer<'info>,
}

#[account]
#[derive(InitSpace)]
pub struct DataAccount {
    pub authority: Pubkey,
    pub value: u64,
    pub bump: u8,
}
```

The `close` constraint zeroes the data, sets the discriminator to a closed marker, and transfers all lamports to the specified account."""
)))

GLAN.append(("events", m(
    "How do I emit events in an Anchor program?",
    """Use `#[event]` and `emit!`:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[event]
pub struct TransferEvent {
    pub from: Pubkey,
    pub to: Pubkey,
    pub amount: u64,
    pub timestamp: i64,
}

#[program]
pub mod events_example {
    use super::*;

    pub fn transfer(ctx: Context<DoTransfer>, amount: u64) -> Result<()> {
        let clock = Clock::get()?;
        // ... transfer logic ...
        emit!(TransferEvent {
            from: ctx.accounts.from.key(),
            to: ctx.accounts.to.key(),
            amount,
            timestamp: clock.unix_timestamp,
        });
        Ok(())
    }
}
```

Client-side:
```typescript
program.addEventListener("TransferEvent", (event, slot) => {
  console.log("Transfer:", event.from.toBase58(), "->", event.to.toBase58());
});
```"""
)))

GLAN.append(("clock", m(
    "How do I use the Solana clock for time-based logic in Anchor?",
    """Use `Clock::get()?`:

```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod time_lock {
    use super::*;

    pub fn lock(ctx: Context<Lock>, unlock_after_secs: i64) -> Result<()> {
        let clock = Clock::get()?;
        let state = &mut ctx.accounts.lock_state;
        state.authority = ctx.accounts.authority.key();
        state.locked_at = clock.unix_timestamp;
        state.unlock_at = clock.unix_timestamp
            .checked_add(unlock_after_secs)
            .ok_or(ErrorCode::MathOverflow)?;
        state.bump = ctx.bumps.lock_state;
        Ok(())
    }

    pub fn unlock(ctx: Context<Unlock>) -> Result<()> {
        let clock = Clock::get()?;
        require!(
            clock.unix_timestamp >= ctx.accounts.lock_state.unlock_at,
            ErrorCode::TooEarly
        );
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct LockState {
    pub authority: Pubkey,
    pub locked_at: i64,
    pub unlock_at: i64,
    pub bump: u8,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Cannot unlock yet")] TooEarly,
    #[msg("Overflow")] MathOverflow,
}
```

`Clock::get()` returns slot, epoch, and unix_timestamp. Timestamps have ~1-2s granularity."""
)))

GLAN.append(("remaining-accounts", m(
    "How do I use remaining_accounts for dynamic account lists in Anchor?",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod multi_send {
    use super::*;

    pub fn distribute(ctx: Context<Distribute>, amount_each: u64) -> Result<()> {
        let recipients = &ctx.remaining_accounts;
        require!(!recipients.is_empty(), DistError::NoRecipients);
        require!(recipients.len() <= 20, DistError::TooMany);

        for recipient_info in recipients.iter() {
            let _token_acc: Account<TokenAccount> = Account::try_from(recipient_info)?;
            token::transfer(
                CpiContext::new(
                    ctx.accounts.token_program.to_account_info(),
                    Transfer {
                        from: ctx.accounts.source.to_account_info(),
                        to: recipient_info.clone(),
                        authority: ctx.accounts.authority.to_account_info(),
                    },
                ),
                amount_each,
            )?;
        }
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Distribute<'info> {
    #[account(mut)]
    pub source: Account<'info, TokenAccount>,
    pub authority: Signer<'info>,
    pub token_program: Program<'info, Token>,
}

#[error_code]
pub enum DistError {
    #[msg("No recipients")] NoRecipients,
    #[msg("Max 20 recipients")] TooMany,
}
```

Always validate remaining accounts with `Account::try_from()` before use."""
)))

GLAN.append(("constraints", m(
    "What are all the common Anchor account constraints?",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token, TokenAccount};

#[derive(Accounts)]
#[instruction(amount: u64)]
pub struct ExampleConstraints<'info> {
    // init: create new account
    #[account(init, payer = payer, space = 8 + MyData::INIT_SPACE,
        seeds = [b"data", payer.key().as_ref()], bump)]
    pub data: Account<'info, MyData>,

    // has_one: check field matches
    #[account(mut, has_one = authority, has_one = mint)]
    pub existing: Account<'info, MyData>,

    // seeds + stored bump
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, Config>,

    // constraint: arbitrary expression
    #[account(constraint = amount <= 1_000_000 @ MyError::TooLarge)]
    pub guarded: Account<'info, MyData>,

    // realloc: resize account
    #[account(mut, realloc = 8 + new_size,
        realloc::payer = payer, realloc::zero = false)]
    pub resizable: Account<'info, MyData>,

    // close: reclaim rent
    #[account(mut, close = authority, has_one = authority)]
    pub closeable: Account<'info, MyData>,

    // token constraints
    #[account(token::mint = mint, token::authority = payer)]
    pub token_acc: Account<'info, TokenAccount>,

    // associated token
    #[account(init, payer = payer,
        associated_token::mint = mint, associated_token::authority = payer)]
    pub ata: Account<'info, TokenAccount>,

    pub mint: Account<'info, Mint>,
    pub authority: Signer<'info>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}
```

Rules: `init` needs `payer`+`space`, store bumps for gas savings, `has_one` checks field==account, `constraint @` gives custom errors."""
)))

GLAN.append(("token-extensions", m(
    "How do I work with Token-2022 (Token Extensions) in Anchor?",
    """Use `token_interface` for Token-2022 compatibility:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token_interface::{Mint, TokenAccount, TokenInterface, TransferChecked, transfer_checked};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod token_ext {
    use super::*;

    pub fn transfer_tokens(ctx: Context<TransferTokens>, amount: u64) -> Result<()> {
        transfer_checked(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                TransferChecked {
                    from: ctx.accounts.from.to_account_info(),
                    mint: ctx.accounts.mint.to_account_info(),
                    to: ctx.accounts.to.to_account_info(),
                    authority: ctx.accounts.authority.to_account_info(),
                },
            ),
            amount,
            ctx.accounts.mint.decimals,
        )
    }
}

#[derive(Accounts)]
pub struct TransferTokens<'info> {
    #[account(mut)]
    pub from: InterfaceAccount<'info, TokenAccount>,
    #[account(mut)]
    pub to: InterfaceAccount<'info, TokenAccount>,
    pub mint: InterfaceAccount<'info, Mint>,
    pub authority: Signer<'info>,
    pub token_program: Interface<'info, TokenInterface>,
}
```

Use `InterfaceAccount`/`Interface` instead of `Account`/`Program` to support both Token and Token-2022."""
)))

GLAN.append(("system", m(
    "How do I transfer SOL in Anchor?",
    """Two methods:

**CPI to system program:**
```rust
use anchor_lang::prelude::*;
use anchor_lang::system_program;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod sol_transfer {
    use super::*;

    pub fn send_sol(ctx: Context<SendSol>, amount: u64) -> Result<()> {
        system_program::transfer(
            CpiContext::new(
                ctx.accounts.system_program.to_account_info(),
                system_program::Transfer {
                    from: ctx.accounts.from.to_account_info(),
                    to: ctx.accounts.to.to_account_info(),
                },
            ),
            amount,
        )
    }

    pub fn send_from_pda(ctx: Context<SendFromPda>, amount: u64) -> Result<()> {
        let seeds: &[&[u8]] = &[b"vault", &[ctx.bumps.vault]];
        system_program::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.system_program.to_account_info(),
                system_program::Transfer {
                    from: ctx.accounts.vault.to_account_info(),
                    to: ctx.accounts.recipient.to_account_info(),
                },
                &[seeds],
            ),
            amount,
        )
    }
}
```

For PDA-owned accounts you can also manipulate lamports directly:
```rust
**source.to_account_info().try_borrow_mut_lamports()? -= amount;
**dest.to_account_info().try_borrow_mut_lamports()? += amount;
```"""
)))

GLAN.append(("init-if-needed", m(
    "How do I use init_if_needed in Anchor?",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod idempotent {
    use super::*;

    pub fn register_or_update(ctx: Context<RegisterOrUpdate>, name: String) -> Result<()> {
        let profile = &mut ctx.accounts.profile;
        if profile.created_at == 0 {
            let clock = Clock::get()?;
            profile.authority = ctx.accounts.user.key();
            profile.created_at = clock.unix_timestamp;
            profile.bump = ctx.bumps.profile;
        }
        profile.name = name;
        profile.update_count += 1;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct RegisterOrUpdate<'info> {
    #[account(
        init_if_needed, payer = user,
        space = 8 + Profile::INIT_SPACE,
        seeds = [b"profile", user.key().as_ref()], bump,
    )]
    pub profile: Account<'info, Profile>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct Profile {
    pub authority: Pubkey,
    #[max_len(32)]
    pub name: String,
    pub created_at: i64,
    pub update_count: u64,
    pub bump: u8,
}
```

Enable in Cargo.toml: `anchor-lang = { version = "0.30", features = ["init-if-needed"] }`. Always check if newly created vs existing to prevent reinit attacks."""
)))

GLAN.append(("defi", m(
    "How do I implement basic staking in Anchor?",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod staking {
    use super::*;

    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        require!(amount > 0, StakeError::ZeroAmount);
        let clock = Clock::get()?;
        let user_stake = &mut ctx.accounts.user_stake;

        if user_stake.staked_amount > 0 {
            let pending = calculate_rewards(user_stake, clock.unix_timestamp);
            user_stake.pending_rewards += pending;
        }

        token::transfer(
            CpiContext::new(ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_token.to_account_info(),
                    to: ctx.accounts.vault.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                }),
            amount,
        )?;

        user_stake.staked_amount += amount;
        user_stake.last_stake_time = clock.unix_timestamp;
        user_stake.authority = ctx.accounts.user.key();
        user_stake.bump = ctx.bumps.user_stake;
        Ok(())
    }

    pub fn unstake(ctx: Context<Unstake>, amount: u64) -> Result<()> {
        let user_stake = &mut ctx.accounts.user_stake;
        require!(amount <= user_stake.staked_amount, StakeError::Insufficient);

        let clock = Clock::get()?;
        user_stake.pending_rewards += calculate_rewards(user_stake, clock.unix_timestamp);
        user_stake.staked_amount -= amount;
        user_stake.last_stake_time = clock.unix_timestamp;

        let bump = ctx.bumps.vault;
        let seeds: &[&[u8]] = &[b"vault", &[bump]];
        token::transfer(
            CpiContext::new_with_signer(ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.vault.to_account_info(),
                    to: ctx.accounts.user_token.to_account_info(),
                    authority: ctx.accounts.vault.to_account_info(),
                }, &[seeds]),
            amount,
        )?;
        Ok(())
    }
}

fn calculate_rewards(stake: &UserStake, now: i64) -> u64 {
    let elapsed = (now - stake.last_stake_time) as u64;
    stake.staked_amount.checked_mul(elapsed).and_then(|v| v.checked_div(86400)).unwrap_or(0)
}

#[account]
#[derive(InitSpace)]
pub struct UserStake {
    pub authority: Pubkey, pub staked_amount: u64,
    pub pending_rewards: u64, pub last_stake_time: i64, pub bump: u8,
}

#[error_code]
pub enum StakeError {
    #[msg("Zero amount")] ZeroAmount,
    #[msg("Insufficient stake")] Insufficient,
}
```"""
)))

GLAN.append(("governance", m(
    "How do I implement on-chain voting in Anchor?",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod voting {
    use super::*;

    pub fn create_proposal(ctx: Context<CreateProposal>, title: String, description: String, voting_end: i64) -> Result<()> {
        let clock = Clock::get()?;
        require!(voting_end > clock.unix_timestamp, VoteError::InvalidDeadline);
        let proposal = &mut ctx.accounts.proposal;
        proposal.creator = ctx.accounts.creator.key();
        proposal.title = title;
        proposal.description = description;
        proposal.yes_votes = 0;
        proposal.no_votes = 0;
        proposal.voting_end = voting_end;
        proposal.proposal_id = ctx.accounts.state.proposal_count;
        proposal.bump = ctx.bumps.proposal;
        ctx.accounts.state.proposal_count += 1;
        Ok(())
    }

    pub fn cast_vote(ctx: Context<CastVote>, vote: bool) -> Result<()> {
        let clock = Clock::get()?;
        let proposal = &mut ctx.accounts.proposal;
        require!(clock.unix_timestamp < proposal.voting_end, VoteError::VotingEnded);

        let ballot = &mut ctx.accounts.ballot;
        require!(!ballot.has_voted, VoteError::AlreadyVoted);

        if vote { proposal.yes_votes += 1; } else { proposal.no_votes += 1; }
        ballot.has_voted = true;
        ballot.vote = vote;
        ballot.voter = ctx.accounts.voter.key();
        ballot.bump = ctx.bumps.ballot;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CastVote<'info> {
    #[account(mut, seeds = [b"proposal", &proposal.proposal_id.to_le_bytes()], bump = proposal.bump)]
    pub proposal: Account<'info, Proposal>,
    #[account(init, payer = voter, space = 8 + Ballot::INIT_SPACE,
        seeds = [b"ballot", proposal.key().as_ref(), voter.key().as_ref()], bump)]
    pub ballot: Account<'info, Ballot>,
    #[account(mut)]
    pub voter: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct Proposal {
    pub creator: Pubkey, #[max_len(64)] pub title: String,
    #[max_len(256)] pub description: String,
    pub yes_votes: u64, pub no_votes: u64,
    pub voting_end: i64, pub proposal_id: u64, pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Ballot { pub voter: Pubkey, pub vote: bool, pub has_voted: bool, pub bump: u8 }

#[error_code]
pub enum VoteError {
    #[msg("Voting ended")] VotingEnded,
    #[msg("Already voted")] AlreadyVoted,
    #[msg("Invalid deadline")] InvalidDeadline,
}
```

The PDA-per-ballot pattern ensures one vote per voter per proposal."""
)))

GLAN.append(("oracles", m(
    "How do I read a Pyth price feed in Anchor?",
    """```rust
use anchor_lang::prelude::*;
use pyth_solana_receiver_sdk::price_update::PriceUpdateV2;

declare_id!("11111111111111111111111111111111");

const STALENESS_THRESHOLD: u64 = 60;

#[program]
pub mod price_oracle {
    use super::*;

    pub fn check_price(ctx: Context<CheckPrice>, feed_id: [u8; 32], min_price: i64) -> Result<()> {
        let price = ctx.accounts.price_feed.get_price_no_older_than(
            &Clock::get()?,
            STALENESS_THRESHOLD,
            &feed_id,
        )?;

        msg!("Price: {} x 10^{}", price.price, price.exponent);

        require!(price.price >= min_price, OracleError::PriceTooLow);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CheckPrice<'info> {
    pub price_feed: Account<'info, PriceUpdateV2>,
    pub payer: Signer<'info>,
}

#[error_code]
pub enum OracleError {
    #[msg("Price below minimum")] PriceTooLow,
}
```

Always check staleness to prevent using outdated prices — stale oracles are a common DeFi exploit vector. Add `pyth-solana-receiver-sdk = "0.4"` to Cargo.toml."""
)))

GLAN.append(("typescript", m(
    "How do I send transactions with priority fees?",
    """```typescript
import { Connection, Transaction, ComputeBudgetProgram, Keypair } from "@solana/web3.js";
import * as anchor from "@coral-xyz/anchor";

async function sendWithPriorityFee(
  connection: Connection, payer: Keypair, program: anchor.Program
) {
  const fees = await connection.getRecentPrioritizationFees();
  const avgFee = fees.length > 0
    ? Math.ceil(fees.reduce((a, b) => a + b.prioritizationFee, 0) / fees.length)
    : 1000;

  const tx = new Transaction();
  tx.add(ComputeBudgetProgram.setComputeUnitLimit({ units: 200_000 }));
  tx.add(ComputeBudgetProgram.setComputeUnitPrice({ microLamports: avgFee }));

  const ix = await program.methods
    .myInstruction(new anchor.BN(100))
    .accounts({ user: payer.publicKey })
    .instruction();
  tx.add(ix);

  const sig = await connection.sendTransaction(tx, [payer]);
  console.log("TX:", sig);
}
```

Fee = `computeUnits * microLamports / 1_000_000` lamports. Set CU limit lower than 200K if your ix uses less."""
)))

GLAN.append(("typescript", m(
    "How do I fetch and filter Anchor accounts in TypeScript?",
    """```typescript
import * as anchor from "@coral-xyz/anchor";
import { PublicKey } from "@solana/web3.js";

const program = new anchor.Program(idl, provider);

// Fetch single by PDA
const [pda] = PublicKey.findProgramAddressSync(
  [Buffer.from("user"), wallet.publicKey.toBuffer()],
  program.programId,
);
const account = await program.account.userData.fetch(pda);

// Fetch all of a type
const all = await program.account.userData.all();

// Filter with memcmp (efficient on-chain filter)
const filtered = await program.account.userData.all([
  {
    memcmp: {
      offset: 8,  // skip 8-byte discriminator
      bytes: wallet.publicKey.toBase58(),
    },
  },
]);

// Subscribe to changes
program.account.userData.subscribe(pda, "confirmed");
program.account.userData.addEventListener("change", (acc) => {
  console.log("Updated:", acc.score.toString());
});
```

Use `memcmp` filters for large datasets. Offset = 8 (discriminator) + preceding field sizes."""
)))

GLAN.append(("errors", m(
    "How do I handle Anchor errors on the client?",
    """```typescript
import { AnchorError } from "@coral-xyz/anchor";

try {
  const tx = await program.methods.riskyOp().rpc();
} catch (err) {
  if (err instanceof AnchorError) {
    console.error("Code:", err.error.errorCode.number);  // e.g. 6001
    console.error("Name:", err.error.errorCode.code);    // e.g. "InsufficientFunds"
    console.error("Msg:", err.error.errorMessage);

    switch (err.error.errorCode.number) {
      case 6001: /* handle insufficient funds */ break;
      case 6002: /* handle invalid amount */ break;
    }
  }

  // Parse from raw logs
  if (err.logs) {
    const parsed = AnchorError.parse(err.logs);
    if (parsed) console.error(parsed.error.errorMessage);
  }
}
```

Anchor errors start at 6000. Use descriptive `#[msg("...")]` on each `#[error_code]` variant."""
)))

GLAN.append(("typescript", m(
    "How do I use versioned transactions with address lookup tables?",
    """```typescript
import { Connection, TransactionMessage, VersionedTransaction, PublicKey, Keypair } from "@solana/web3.js";

async function sendVersionedTx(
  connection: Connection, payer: Keypair,
  instructions: any[], lookupTableAddr?: PublicKey
) {
  let lookupTables = [];
  if (lookupTableAddr) {
    const result = await connection.getAddressLookupTable(lookupTableAddr);
    if (result.value) lookupTables.push(result.value);
  }

  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");

  const messageV0 = new TransactionMessage({
    payerKey: payer.publicKey,
    recentBlockhash: blockhash,
    instructions,
  }).compileToV0Message(lookupTables);

  const tx = new VersionedTransaction(messageV0);
  tx.sign([payer]);

  const sig = await connection.sendTransaction(tx, { maxRetries: 3 });
  await connection.confirmTransaction({ signature: sig, blockhash, lastValidBlockHeight }, "confirmed");
  return sig;
}
```

Lookup tables reduce tx size from 32 bytes to 1 byte per referenced account. Essential for complex DeFi swaps."""
)))

GLAN.append(("security", m(
    "What are the key Anchor security patterns?",
    """**1. Validate signers:**
```rust
#[account(mut, has_one = authority)]
pub state: Account<'info, State>,
pub authority: Signer<'info>,  // enforces signature
```

**2. Checked math:**
```rust
let total = a.checked_add(b).ok_or(MyError::Overflow)?;
```

**3. Full PDA validation:**
```rust
#[account(seeds = [b"vault", authority.key().as_ref()], bump = vault.bump)]
pub vault: Account<'info, Vault>,
```

**4. Prevent reinit:**
```rust
// Anchor's `init` prevents reinit via discriminator
// For init_if_needed, add your own check:
require!(state.created_at == 0, MyError::AlreadyInit);
```

**5. Close safely:**
```rust
#[account(mut, close = authority, has_one = authority)]
pub closeable: Account<'info, Data>,
```

**6. Validate programs:**
```rust
pub token_program: Program<'info, Token>,  // Anchor checks ID
// NOT: pub token_program: UncheckedAccount<'info>
```

**7. Validate token accounts:**
```rust
#[account(
    constraint = user_token.owner == user.key() @ MyError::WrongOwner,
    constraint = user_token.mint == expected_mint.key() @ MyError::WrongMint,
)]
pub user_token: Account<'info, TokenAccount>,
```

Principle: validate everything at the account level, not in instruction logic."""
)))

GLAN.append(("migration", m(
    "How do I migrate from Anchor 0.29 to 0.30+?",
    """Key changes:

**1. Crate source:** Now on crates.io from `solana-foundation/anchor`:
```toml
anchor-lang = "0.30"  # was git = "https://github.com/coral-xyz/anchor"
```

**2. Space with InitSpace:**
```rust
// OLD: space = 8 + 32 + 8
// NEW:
#[derive(InitSpace)]
pub struct Data { pub authority: Pubkey, pub value: u64 }
// space = 8 + Data::INIT_SPACE
```

**3. Bump access:**
```rust
// OLD: let bump = *ctx.bumps.get("my_pda").unwrap();
// NEW:
let bump = ctx.bumps.my_pda;
```

**4. CLI:**
```bash
avm install latest && avm use latest
```

**5. Client:**
```json
"@coral-xyz/anchor": "^0.30.0"
```

Most programs need minimal changes."""
)))

GLAN.append(("concepts", m(
    "Explain the Solana account model.",
    """Solana separates programs (code) from accounts (data). Programs are stateless.

**Account structure:**
```
Account { key: Pubkey, lamports: u64, data: Vec<u8>, owner: Pubkey, executable: bool }
```

**Key concepts:**
1. **Ownership:** Only the owner program can modify `data`. Anyone can credit lamports.
2. **Programs are stateless:** All state is passed in as accounts.
3. **PDAs:** Deterministic addresses from seeds. No private key — only the program can sign.
4. **Rent:** Accounts need minimum SOL (~0.00089/KB/epoch). Anchor's `init` makes accounts rent-exempt.
5. **Parallelism:** All accessed accounts declared upfront, enabling parallel execution of non-overlapping transactions.

This is why Solana is fast: the runtime knows exactly which accounts each tx touches."""
)))

GLAN.append(("concepts", m(
    "What are compute units in Solana?",
    """Every instruction consumes compute units (CU). Default: 200K per ix, max 1.4M per tx.

**Common costs:** Ed25519 verify ~25K, token transfer ~4K, PDA derivation ~1.5K, account create ~5K.

**Set budget client-side:**
```typescript
import { ComputeBudgetProgram } from "@solana/web3.js";
tx.add(ComputeBudgetProgram.setComputeUnitLimit({ units: 400_000 }));
tx.add(ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 1000 }));
```

**Optimization tips:**
- Use zero-copy for large accounts
- Use stored bumps (saves ~1500 CU per PDA)
- Batch operations in one instruction
- Minimize logs in production
- Use `checked_*` for safe math"""
)))

GLAN.append(("tooling", m(
    "How do I use the Anchor IDL?",
    """```bash
anchor build  # generates target/idl/my_program.json + target/types/my_program.ts
```

**TypeScript usage:**
```typescript
import { Program } from "@coral-xyz/anchor";
import { MyProgram } from "../target/types/my_program";
import idl from "../target/idl/my_program.json";

const program = new Program<MyProgram>(idl as any, provider);

// Typed method calls
await program.methods.initialize("Hello", new anchor.BN(42))
    .accounts({ dataAccount: pda, user: wallet.publicKey, systemProgram: SystemProgram.programId })
    .rpc();

// Typed account fetch
const data = await program.account.dataAccount.fetch(pda);
```

**Deploy IDL on-chain:**
```bash
anchor idl init --filepath target/idl/my_program.json <PROGRAM_ID>
```

The IDL enables Solana explorers to decode your transactions automatically."""
)))


# ═══════════════════════════════════════════════════════════════════════════════
# EVOL-INSTRUCT: Progressive complexity
# ═══════════════════════════════════════════════════════════════════════════════

EVOL = []

# Base: Counter program
EVOL.append(("counter", "L0", m(
    "Write a simple Anchor program that stores a counter and lets users increment it.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod counter {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.authority = ctx.accounts.user.key();
        counter.count = 0;
        Ok(())
    }

    pub fn increment(ctx: Context<Increment>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.count = counter.count.checked_add(1).ok_or(ErrorCode::Overflow)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(init, payer = user, space = 8 + Counter::INIT_SPACE)]
    pub counter: Account<'info, Counter>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Increment<'info> {
    #[account(mut)]
    pub counter: Account<'info, Counter>,
}

#[account]
#[derive(InitSpace)]
pub struct Counter {
    pub authority: Pubkey,
    pub count: u64,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Counter overflow")] Overflow,
}
```"""
)))

EVOL.append(("counter", "L1", m(
    "Enhance the counter program: only the authority should be able to increment. Add a decrement function with underflow protection.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod counter {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.authority = ctx.accounts.user.key();
        counter.count = 0;
        Ok(())
    }

    pub fn increment(ctx: Context<Modify>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.count = counter.count.checked_add(1).ok_or(CounterError::Overflow)?;
        Ok(())
    }

    pub fn decrement(ctx: Context<Modify>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.count = counter.count.checked_sub(1).ok_or(CounterError::Underflow)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(init, payer = user, space = 8 + Counter::INIT_SPACE)]
    pub counter: Account<'info, Counter>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Modify<'info> {
    #[account(constraint = authority.key() == counter.authority @ CounterError::Unauthorized)]
    pub authority: Signer<'info>,
    #[account(mut)]
    pub counter: Account<'info, Counter>,
}

#[account]
#[derive(InitSpace)]
pub struct Counter {
    pub authority: Pubkey,
    pub count: u64,
}

#[error_code]
pub enum CounterError {
    #[msg("Unauthorized")] Unauthorized,
    #[msg("Overflow")] Overflow,
    #[msg("Underflow — counter is already at 0")] Underflow,
}
```

The `Modify` accounts struct now requires `authority` to be a signer that matches `counter.authority`. This prevents anyone else from modifying the counter."""
)))

EVOL.append(("counter", "L2", m(
    "Further evolve the counter: use a PDA so each user gets their own counter, add transfer_authority to hand off ownership.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod counter {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.authority = ctx.accounts.user.key();
        counter.count = 0;
        counter.bump = ctx.bumps.counter;
        Ok(())
    }

    pub fn increment(ctx: Context<Modify>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.count = counter.count.checked_add(1).ok_or(CounterError::Overflow)?;
        Ok(())
    }

    pub fn decrement(ctx: Context<Modify>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.count = counter.count.checked_sub(1).ok_or(CounterError::Underflow)?;
        Ok(())
    }

    pub fn transfer_authority(ctx: Context<TransferAuth>, new_authority: Pubkey) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.authority = new_authority;
        msg!("Authority transferred to {}", new_authority);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(
        init,
        payer = user,
        space = 8 + Counter::INIT_SPACE,
        seeds = [b"counter", user.key().as_ref()],
        bump,
    )]
    pub counter: Account<'info, Counter>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Modify<'info> {
    #[account(constraint = authority.key() == counter.authority @ CounterError::Unauthorized)]
    pub authority: Signer<'info>,
    #[account(
        mut,
        seeds = [b"counter", counter.authority.as_ref()],
        bump = counter.bump,
    )]
    pub counter: Account<'info, Counter>,
}

#[derive(Accounts)]
pub struct TransferAuth<'info> {
    #[account(constraint = authority.key() == counter.authority @ CounterError::Unauthorized)]
    pub authority: Signer<'info>,
    #[account(mut)]
    pub counter: Account<'info, Counter>,
}

#[account]
#[derive(InitSpace)]
pub struct Counter {
    pub authority: Pubkey,
    pub count: u64,
    pub bump: u8,
}

#[error_code]
pub enum CounterError {
    #[msg("Unauthorized")] Unauthorized,
    #[msg("Overflow")] Overflow,
    #[msg("Underflow")] Underflow,
}
```

Now each user gets a unique counter via PDA seeds `[b"counter", user.key()]`. The `transfer_authority` instruction allows handing off ownership."""
)))

# ── Escrow evolution ────────────────────────────────────────────────────────

EVOL.append(("escrow", "L0", m(
    "Write a simple token escrow in Anchor where a maker deposits tokens and a taker can claim them.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer, Mint};
use anchor_spl::associated_token::AssociatedToken;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod escrow {
    use super::*;

    pub fn create(ctx: Context<Create>, amount: u64) -> Result<()> {
        require!(amount > 0, EscrowError::ZeroAmount);

        // Transfer maker's tokens to escrow vault
        let cpi_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.maker_token.to_account_info(),
                to: ctx.accounts.escrow_vault.to_account_info(),
                authority: ctx.accounts.maker.to_account_info(),
            },
        );
        token::transfer(cpi_ctx, amount)?;

        let escrow = &mut ctx.accounts.escrow;
        escrow.maker = ctx.accounts.maker.key();
        escrow.mint = ctx.accounts.mint.key();
        escrow.amount = amount;
        escrow.bump = ctx.bumps.escrow;
        Ok(())
    }

    pub fn claim(ctx: Context<Claim>) -> Result<()> {
        let escrow = &ctx.accounts.escrow;
        let seeds = &[b"escrow".as_ref(), escrow.maker.as_ref(), &[escrow.bump]];

        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.escrow_vault.to_account_info(),
                to: ctx.accounts.taker_token.to_account_info(),
                authority: ctx.accounts.escrow.to_account_info(),
            },
            &[seeds],
        );
        token::transfer(cpi_ctx, escrow.amount)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Create<'info> {
    #[account(mut)]
    pub maker: Signer<'info>,
    pub mint: Account<'info, Mint>,
    #[account(
        init, payer = maker, space = 8 + Escrow::INIT_SPACE,
        seeds = [b"escrow", maker.key().as_ref()], bump,
    )]
    pub escrow: Account<'info, Escrow>,
    #[account(init, payer = maker, token::mint = mint, token::authority = escrow)]
    pub escrow_vault: Account<'info, TokenAccount>,
    #[account(mut, token::mint = mint, token::authority = maker)]
    pub maker_token: Account<'info, TokenAccount>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Claim<'info> {
    pub taker: Signer<'info>,
    #[account(mut, close = maker, seeds = [b"escrow", escrow.maker.as_ref()], bump = escrow.bump)]
    pub escrow: Account<'info, Escrow>,
    /// CHECK: receiving rent
    #[account(mut, constraint = maker.key() == escrow.maker)]
    pub maker: UncheckedAccount<'info>,
    #[account(mut, token::mint = escrow.mint, token::authority = escrow)]
    pub escrow_vault: Account<'info, TokenAccount>,
    #[account(mut, token::mint = escrow.mint)]
    pub taker_token: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[account]
#[derive(InitSpace)]
pub struct Escrow {
    pub maker: Pubkey,
    pub mint: Pubkey,
    pub amount: u64,
    pub bump: u8,
}

#[error_code]
pub enum EscrowError {
    #[msg("Amount must be > 0")] ZeroAmount,
}
```"""
)))

EVOL.append(("escrow", "L1", m(
    "Add a timelock to the escrow: taker can only claim after a specified deadline, and maker can cancel before the deadline.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer, Mint};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod escrow {
    use super::*;

    pub fn create(ctx: Context<Create>, amount: u64, unlock_time: i64) -> Result<()> {
        require!(amount > 0, EscrowError::ZeroAmount);
        let now = Clock::get()?.unix_timestamp;
        require!(unlock_time > now, EscrowError::InvalidUnlockTime);

        let cpi_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.maker_token.to_account_info(),
                to: ctx.accounts.escrow_vault.to_account_info(),
                authority: ctx.accounts.maker.to_account_info(),
            },
        );
        token::transfer(cpi_ctx, amount)?;

        let escrow = &mut ctx.accounts.escrow;
        escrow.maker = ctx.accounts.maker.key();
        escrow.mint = ctx.accounts.mint.key();
        escrow.amount = amount;
        escrow.unlock_time = unlock_time;
        escrow.bump = ctx.bumps.escrow;
        Ok(())
    }

    pub fn claim(ctx: Context<Claim>) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        require!(now >= ctx.accounts.escrow.unlock_time, EscrowError::TooEarly);

        let escrow = &ctx.accounts.escrow;
        let seeds = &[b"escrow".as_ref(), escrow.maker.as_ref(), &[escrow.bump]];

        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.escrow_vault.to_account_info(),
                to: ctx.accounts.taker_token.to_account_info(),
                authority: ctx.accounts.escrow.to_account_info(),
            },
            &[seeds],
        );
        token::transfer(cpi_ctx, escrow.amount)?;
        Ok(())
    }

    pub fn cancel(ctx: Context<Cancel>) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        require!(now < ctx.accounts.escrow.unlock_time, EscrowError::AlreadyUnlocked);

        let escrow = &ctx.accounts.escrow;
        let seeds = &[b"escrow".as_ref(), escrow.maker.as_ref(), &[escrow.bump]];

        // Return tokens to maker
        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.escrow_vault.to_account_info(),
                to: ctx.accounts.maker_token.to_account_info(),
                authority: ctx.accounts.escrow.to_account_info(),
            },
            &[seeds],
        );
        token::transfer(cpi_ctx, escrow.amount)?;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Escrow {
    pub maker: Pubkey,
    pub mint: Pubkey,
    pub amount: u64,
    pub unlock_time: i64,
    pub bump: u8,
}

#[error_code]
pub enum EscrowError {
    #[msg("Amount must be > 0")] ZeroAmount,
    #[msg("Unlock time must be in the future")] InvalidUnlockTime,
    #[msg("Escrow has not reached unlock time yet")] TooEarly,
    #[msg("Cannot cancel after unlock time")] AlreadyUnlocked,
}
// Account structs for Create/Claim/Cancel follow the same pattern as L0
// with added time checks via constraints or instruction logic
```

The maker can `cancel` before the deadline to reclaim tokens. The taker can only `claim` after `unlock_time`."""
)))


# ── Additional Evol chains ─────────────────────────────────────────────────

EVOL.append(("token-vault", "L0", m(
    "Create a simple SPL token vault that lets users deposit tokens.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer, Mint};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod vault {
    use super::*;

    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        require!(amount > 0, VaultError::ZeroAmount);
        token::transfer(
            CpiContext::new(ctx.accounts.token_program.to_account_info(),
                Transfer { from: ctx.accounts.user_token.to_account_info(),
                    to: ctx.accounts.vault_token.to_account_info(),
                    authority: ctx.accounts.user.to_account_info() }),
            amount,
        )?;
        let receipt = &mut ctx.accounts.receipt;
        receipt.depositor = ctx.accounts.user.key();
        receipt.amount = amount;
        receipt.mint = ctx.accounts.mint.key();
        receipt.bump = ctx.bumps.receipt;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Deposit<'info> {
    #[account(init_if_needed, payer = user, space = 8 + Receipt::INIT_SPACE,
        seeds = [b"receipt", user.key().as_ref(), mint.key().as_ref()], bump)]
    pub receipt: Account<'info, Receipt>,
    #[account(mut, associated_token::mint = mint, associated_token::authority = user)]
    pub user_token: Account<'info, TokenAccount>,
    #[account(mut, seeds = [b"vault", mint.key().as_ref()], bump)]
    pub vault_token: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct Receipt { pub depositor: Pubkey, pub amount: u64, pub mint: Pubkey, pub bump: u8 }

#[error_code]
pub enum VaultError { #[msg("Amount must be > 0")] ZeroAmount }
```"""
)))

EVOL.append(("token-vault", "L1", m(
    "Extend the vault with withdrawals and a 24h timelock.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer, Mint};

declare_id!("11111111111111111111111111111111");
const LOCK_DURATION: i64 = 86400;

#[program]
pub mod vault {
    use super::*;

    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        require!(amount > 0, VaultError::ZeroAmount);
        let clock = Clock::get()?;
        token::transfer(
            CpiContext::new(ctx.accounts.token_program.to_account_info(),
                Transfer { from: ctx.accounts.user_token.to_account_info(),
                    to: ctx.accounts.vault_token.to_account_info(),
                    authority: ctx.accounts.user.to_account_info() }),
            amount)?;
        let r = &mut ctx.accounts.receipt;
        r.amount = r.amount.checked_add(amount).ok_or(VaultError::Overflow)?;
        r.deposited_at = clock.unix_timestamp;
        r.depositor = ctx.accounts.user.key();
        r.mint = ctx.accounts.mint.key();
        r.bump = ctx.bumps.receipt;
        Ok(())
    }

    pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
        let clock = Clock::get()?;
        let r = &mut ctx.accounts.receipt;
        require!(amount <= r.amount, VaultError::Insufficient);
        require!(clock.unix_timestamp >= r.deposited_at + LOCK_DURATION, VaultError::Locked);

        let mint_key = ctx.accounts.mint.key();
        let seeds: &[&[u8]] = &[b"vault", mint_key.as_ref(), &[ctx.bumps.vault_token]];
        token::transfer(
            CpiContext::new_with_signer(ctx.accounts.token_program.to_account_info(),
                Transfer { from: ctx.accounts.vault_token.to_account_info(),
                    to: ctx.accounts.user_token.to_account_info(),
                    authority: ctx.accounts.vault_token.to_account_info() },
                &[seeds]),
            amount)?;
        r.amount -= amount;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Receipt {
    pub depositor: Pubkey, pub amount: u64, pub mint: Pubkey,
    pub deposited_at: i64, pub bump: u8,
}

#[error_code]
pub enum VaultError {
    #[msg("Zero")] ZeroAmount, #[msg("Insufficient")] Insufficient,
    #[msg("Locked 24h")] Locked, #[msg("Overflow")] Overflow,
}
```"""
)))

EVOL.append(("voting", "L0", m(
    "Create a simple yes/no voting program.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod voting {
    use super::*;

    pub fn create_poll(ctx: Context<CreatePoll>, question: String) -> Result<()> {
        let poll = &mut ctx.accounts.poll;
        poll.creator = ctx.accounts.creator.key();
        poll.question = question;
        poll.yes_count = 0;
        poll.no_count = 0;
        poll.bump = ctx.bumps.poll;
        Ok(())
    }

    pub fn vote(ctx: Context<Vote>, choice: bool) -> Result<()> {
        let poll = &mut ctx.accounts.poll;
        let ballot = &mut ctx.accounts.ballot;
        ballot.voter = ctx.accounts.voter.key();
        ballot.choice = choice;
        ballot.bump = ctx.bumps.ballot;
        if choice { poll.yes_count += 1; } else { poll.no_count += 1; }
        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(question: String)]
pub struct CreatePoll<'info> {
    #[account(init, payer = creator, space = 8 + Poll::INIT_SPACE,
        seeds = [b"poll", creator.key().as_ref()], bump)]
    pub poll: Account<'info, Poll>,
    #[account(mut)]
    pub creator: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Vote<'info> {
    #[account(mut)]
    pub poll: Account<'info, Poll>,
    #[account(init, payer = voter, space = 8 + Ballot::INIT_SPACE,
        seeds = [b"ballot", poll.key().as_ref(), voter.key().as_ref()], bump)]
    pub ballot: Account<'info, Ballot>,
    #[account(mut)]
    pub voter: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct Poll { pub creator: Pubkey, #[max_len(128)] pub question: String, pub yes_count: u64, pub no_count: u64, pub bump: u8 }

#[account]
#[derive(InitSpace)]
pub struct Ballot { pub voter: Pubkey, pub choice: bool, pub bump: u8 }
```"""
)))

EVOL.append(("voting", "L1", m(
    "Add deadline enforcement and vote changing to the voting program.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod voting {
    use super::*;

    pub fn create_poll(ctx: Context<CreatePoll>, question: String, deadline: i64) -> Result<()> {
        let clock = Clock::get()?;
        require!(deadline > clock.unix_timestamp, VoteError::InvalidDeadline);
        let poll = &mut ctx.accounts.poll;
        poll.creator = ctx.accounts.creator.key();
        poll.question = question;
        poll.yes_count = 0;
        poll.no_count = 0;
        poll.deadline = deadline;
        poll.total_voters = 0;
        poll.bump = ctx.bumps.poll;
        Ok(())
    }

    pub fn cast_vote(ctx: Context<CastVote>, choice: bool) -> Result<()> {
        let clock = Clock::get()?;
        let poll = &mut ctx.accounts.poll;
        require!(clock.unix_timestamp < poll.deadline, VoteError::PollEnded);

        let ballot = &mut ctx.accounts.ballot;
        if ballot.has_voted {
            if ballot.choice && !choice { poll.yes_count -= 1; poll.no_count += 1; }
            else if !ballot.choice && choice { poll.no_count -= 1; poll.yes_count += 1; }
        } else {
            if choice { poll.yes_count += 1; } else { poll.no_count += 1; }
            poll.total_voters += 1;
            ballot.has_voted = true;
        }
        ballot.voter = ctx.accounts.voter.key();
        ballot.choice = choice;
        ballot.voted_at = clock.unix_timestamp;
        ballot.bump = ctx.bumps.ballot;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CastVote<'info> {
    #[account(mut)]
    pub poll: Account<'info, Poll>,
    #[account(init_if_needed, payer = voter, space = 8 + Ballot::INIT_SPACE,
        seeds = [b"ballot", poll.key().as_ref(), voter.key().as_ref()], bump)]
    pub ballot: Account<'info, Ballot>,
    #[account(mut)]
    pub voter: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct Poll {
    pub creator: Pubkey, #[max_len(128)] pub question: String,
    pub yes_count: u64, pub no_count: u64, pub deadline: i64,
    pub total_voters: u64, pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Ballot {
    pub voter: Pubkey, pub choice: bool, pub has_voted: bool,
    pub voted_at: i64, pub bump: u8,
}

#[error_code]
pub enum VoteError {
    #[msg("Poll ended")] PollEnded,
    #[msg("Invalid deadline")] InvalidDeadline,
}
```"""
)))


# ═══════════════════════════════════════════════════════════════════════════════
# Build records and write
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # GLAN records
    glan_records = [rec(content, "glan", cat) for cat, content in GLAN]
    glan_path = OUT_DIR / "synthetic-glan.jsonl"
    glan_count = write_jsonl(glan_records, glan_path)
    print(f"✓ {glan_count} GLAN records → {glan_path.name}")

    # Evol-Instruct records
    evol_records = [
        Record(
            id=Record.make_id(content),
            source="synthetic/evol-instruct",
            source_type="qa",
            content=content,
            language="rust",
            license="synthetic-claude",
            metadata={"method": "evol-instruct", "base_task": task, "level": level, "collected_at": "2026-03-27"},
        )
        for task, level, content in EVOL
    ]
    evol_path = OUT_DIR / "synthetic-evol-instruct.jsonl"
    evol_count = write_jsonl(evol_records, evol_path)
    print(f"✓ {evol_count} Evol-Instruct records → {evol_path.name}")

    total = glan_count + evol_count
    print(f"\nTotal synthetic records: {total}")


if __name__ == "__main__":
    main()
