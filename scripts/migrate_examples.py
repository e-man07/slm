#!/usr/bin/env python3
"""Generate Anchor migration examples (old → new patterns).

Creates 50-100 conversion pairs showing:
- coral-xyz/anchor → solana-foundation/anchor
- declare_id! → declare_program!
- Old account validation → modern Anchor 0.30+ constraints

These are used as training data to teach the model modern patterns.

Usage:
    python scripts/migrate_examples.py
    python scripts/migrate_examples.py --count 100
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from schema import Record, today_str, write_jsonl

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Migration pairs: (description, old_code, new_code)
MIGRATION_PAIRS = [
    (
        "Migrate declare_id! to declare_program! macro",
        '''use anchor_lang::prelude::*;

declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS");

#[program]
pub mod my_program {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        Ok(())
    }
}''',
        '''use anchor_lang::prelude::*;

declare_program!(my_program);

#[program]
pub mod my_program {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        Ok(())
    }
}''',
    ),
    (
        "Migrate Cargo.toml from coral-xyz to solana-foundation",
        '''[dependencies]
anchor-lang = { version = "0.29.0", features = ["init-if-needed"] }
anchor-spl = "0.29.0"

# Old repo reference
# https://github.com/coral-xyz/anchor''',
        '''[dependencies]
anchor-lang = { version = "0.30.1", features = ["init-if-needed"] }
anchor-spl = "0.30.1"

# New repo reference
# https://github.com/solana-foundation/anchor''',
    ),
    (
        "Migrate account validation from manual checks to Anchor constraints",
        '''pub fn transfer(ctx: Context<Transfer>, amount: u64) -> Result<()> {
    // Old pattern: manual validation
    if ctx.accounts.authority.key() != ctx.accounts.vault.authority {
        return Err(ErrorCode::Unauthorized.into());
    }
    if ctx.accounts.vault.amount < amount {
        return Err(ErrorCode::InsufficientFunds.into());
    }

    // Transfer logic
    let vault = &mut ctx.accounts.vault;
    vault.amount -= amount;
    Ok(())
}

#[derive(Accounts)]
pub struct Transfer<'info> {
    pub authority: Signer<'info>,
    #[account(mut)]
    pub vault: Account<'info, Vault>,
}''',
        '''pub fn transfer(ctx: Context<Transfer>, amount: u64) -> Result<()> {
    // Modern pattern: Anchor constraints handle validation
    let vault = &mut ctx.accounts.vault;
    vault.amount = vault.amount.checked_sub(amount)
        .ok_or(ErrorCode::InsufficientFunds)?;
    Ok(())
}

#[derive(Accounts)]
pub struct Transfer<'info> {
    #[account(
        constraint = authority.key() == vault.authority @ ErrorCode::Unauthorized
    )]
    pub authority: Signer<'info>,
    #[account(
        mut,
        constraint = vault.amount >= amount @ ErrorCode::InsufficientFunds
    )]
    pub vault: Account<'info, Vault>,
}''',
    ),
    (
        "Migrate PDA derivation from manual to Anchor seeds constraint",
        '''pub fn create_user_account(ctx: Context<CreateUser>, name: String) -> Result<()> {
    // Old pattern: manual PDA derivation
    let (pda, bump) = Pubkey::find_program_address(
        &[b"user", ctx.accounts.authority.key().as_ref()],
        ctx.program_id,
    );

    require!(pda == ctx.accounts.user_account.key(), ErrorCode::InvalidPDA);

    let user = &mut ctx.accounts.user_account;
    user.authority = ctx.accounts.authority.key();
    user.name = name;
    user.bump = bump;
    Ok(())
}''',
        '''pub fn create_user_account(ctx: Context<CreateUser>, name: String) -> Result<()> {
    // Modern pattern: Anchor handles PDA derivation + validation via seeds
    let user = &mut ctx.accounts.user_account;
    user.authority = ctx.accounts.authority.key();
    user.name = name;
    user.bump = ctx.bumps.user_account;
    Ok(())
}

#[derive(Accounts)]
pub struct CreateUser<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        init,
        payer = authority,
        space = 8 + UserAccount::INIT_SPACE,
        seeds = [b"user", authority.key().as_ref()],
        bump,
    )]
    pub user_account: Account<'info, UserAccount>,
    pub system_program: Program<'info, System>,
}''',
    ),
    (
        "Migrate old error handling to modern Anchor error_code",
        '''// Old pattern: manual error enum
#[error]
pub enum ErrorCode {
    #[msg("You are not authorized")]
    Unauthorized,
    #[msg("Insufficient funds")]
    InsufficientFunds,
}''',
        '''// Modern Anchor 0.30+ pattern
#[error_code]
pub enum ErrorCode {
    #[msg("You are not authorized")]
    Unauthorized,
    #[msg("Insufficient funds")]
    InsufficientFunds,
}''',
    ),
    (
        "Migrate account close from manual to Anchor close constraint",
        '''pub fn close_account(ctx: Context<CloseAccount>) -> Result<()> {
    // Old pattern: manual lamport transfer for closing
    let dest_lamports = ctx.accounts.destination.lamports();
    let close_lamports = ctx.accounts.account_to_close.to_account_info().lamports();

    **ctx.accounts.destination.lamports.borrow_mut() = dest_lamports
        .checked_add(close_lamports)
        .unwrap();
    **ctx.accounts.account_to_close.to_account_info().lamports.borrow_mut() = 0;

    let mut data = ctx.accounts.account_to_close.to_account_info().data.borrow_mut();
    data.fill(0);

    Ok(())
}''',
        '''pub fn close_account(_ctx: Context<CloseAccount>) -> Result<()> {
    // Modern pattern: Anchor close constraint handles everything
    Ok(())
}

#[derive(Accounts)]
pub struct CloseAccount<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        mut,
        close = authority,
        has_one = authority,
    )]
    pub account_to_close: Account<'info, MyAccount>,
}''',
    ),
    (
        "Migrate from AccountInfo to typed Account wrappers",
        '''#[derive(Accounts)]
pub struct DoSomething<'info> {
    // Old pattern: raw AccountInfo requires manual deserialization
    /// CHECK: manually validated
    pub token_account: AccountInfo<'info>,
    /// CHECK: manually validated
    pub mint: AccountInfo<'info>,
    pub authority: Signer<'info>,
}

pub fn do_something(ctx: Context<DoSomething>) -> Result<()> {
    let token_data = TokenAccount::try_deserialize(
        &mut &ctx.accounts.token_account.data.borrow()[..]
    )?;
    require!(token_data.mint == ctx.accounts.mint.key(), ErrorCode::InvalidMint);
    Ok(())
}''',
        '''#[derive(Accounts)]
pub struct DoSomething<'info> {
    // Modern pattern: typed wrappers with built-in validation
    #[account(
        token::mint = mint,
        token::authority = authority,
    )]
    pub token_account: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    pub authority: Signer<'info>,
}

pub fn do_something(_ctx: Context<DoSomething>) -> Result<()> {
    // All validation handled by Anchor constraints above
    Ok(())
}''',
    ),
    (
        "Migrate CPI from manual invoke to Anchor CpiContext",
        '''// Old pattern: manual CPI with invoke_signed
pub fn transfer_tokens(ctx: Context<TransferTokens>, amount: u64) -> Result<()> {
    let ix = spl_token::instruction::transfer(
        &spl_token::ID,
        ctx.accounts.from.key,
        ctx.accounts.to.key,
        ctx.accounts.authority.key,
        &[],
        amount,
    )?;

    let seeds = &[b"vault", &[ctx.accounts.vault.bump]];
    let signer_seeds = &[&seeds[..]];

    solana_program::program::invoke_signed(
        &ix,
        &[
            ctx.accounts.from.to_account_info(),
            ctx.accounts.to.to_account_info(),
            ctx.accounts.authority.to_account_info(),
        ],
        signer_seeds,
    )?;
    Ok(())
}''',
        '''// Modern pattern: Anchor CpiContext with anchor-spl
pub fn transfer_tokens(ctx: Context<TransferTokens>, amount: u64) -> Result<()> {
    let seeds = &[b"vault".as_ref(), &[ctx.accounts.vault.bump]];
    let signer_seeds = &[&seeds[..]];

    let cpi_ctx = CpiContext::new_with_signer(
        ctx.accounts.token_program.to_account_info(),
        Transfer {
            from: ctx.accounts.from.to_account_info(),
            to: ctx.accounts.to.to_account_info(),
            authority: ctx.accounts.vault.to_account_info(),
        },
        signer_seeds,
    );

    anchor_spl::token::transfer(cpi_ctx, amount)?;
    Ok(())
}''',
    ),
    (
        "Migrate account space calculation to INIT_SPACE derive",
        '''// Old pattern: manual space calculation
#[account]
pub struct UserProfile {
    pub authority: Pubkey,    // 32
    pub name: String,         // 4 + 50
    pub level: u8,            // 1
    pub score: u64,           // 8
}

// Manual: 8 (discriminator) + 32 + 4 + 50 + 1 + 8 = 103
const USER_PROFILE_SPACE: usize = 8 + 32 + 4 + 50 + 1 + 8;

#[derive(Accounts)]
pub struct CreateProfile<\'info> {
    #[account(init, payer = authority, space = USER_PROFILE_SPACE)]
    pub profile: Account<\'info, UserProfile>,
}''',
        '''// Modern pattern: InitSpace derive macro
#[account]
#[derive(InitSpace)]
pub struct UserProfile {
    pub authority: Pubkey,
    #[max_len(50)]
    pub name: String,
    pub level: u8,
    pub score: u64,
}

#[derive(Accounts)]
pub struct CreateProfile<\'info> {
    #[account(init, payer = authority, space = 8 + UserProfile::INIT_SPACE)]
    pub profile: Account<\'info, UserProfile>,
    #[account(mut)]
    pub authority: Signer<\'info>,
    pub system_program: Program<\'info, System>,
}''',
    ),
    (
        "Migrate deprecated load_instruction_at to get_instruction_relative",
        '''// Old pattern (DEPRECATED): load_instruction_at
use solana_program::sysvar::instructions::load_instruction_at;

pub fn verify_ed25519(ctx: Context<Verify>) -> Result<()> {
    let ix = load_instruction_at(0, &ctx.accounts.instructions)?;
    // Verify the instruction...
    Ok(())
}''',
        '''// Modern pattern: get_instruction_relative
use solana_program::sysvar::instructions::get_instruction_relative;

pub fn verify_ed25519(ctx: Context<Verify>) -> Result<()> {
    let ix = get_instruction_relative(-1, &ctx.accounts.instructions)?;
    // Verify the instruction...
    Ok(())
}''',
    ),
]


@app.command()
def generate(
    count: int = typer.Option(50, help="Target number of migration examples (includes base + variations)"),
):
    """Generate Anchor old→new migration example pairs."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    records: list[Record] = []

    for desc, old_code, new_code in MIGRATION_PAIRS:
        # SFT format: user asks how to migrate, assistant shows the conversion
        content = json.dumps(
            [
                {
                    "role": "system",
                    "content": "You are an expert Solana/Anchor developer specializing in helping developers migrate to modern Anchor 0.30+ patterns.",
                },
                {
                    "role": "user",
                    "content": f"How do I migrate this old Anchor code to modern patterns?\n\n```rust\n{old_code}\n```",
                },
                {
                    "role": "assistant",
                    "content": f"Here's the migration to modern Anchor 0.30+ patterns ({desc}):\n\n```rust\n{new_code}\n```\n\nKey changes:\n- Uses modern Anchor 0.30+ conventions from the solana-foundation/anchor repository\n- Leverages Anchor's built-in constraint system for validation\n- Reduces manual boilerplate and improves safety",
                },
            ],
            ensure_ascii=False,
        )

        record = Record(
            id=Record.make_id(content),
            source="hand-curated/migration-examples",
            source_type="qa",
            content=content,
            language="rust",
            license="Apache-2.0",
            metadata={
                "description": desc,
                "anchor_style": "modern",
                "collected_at": today_str(),
                "migration_type": "old-to-new",
            },
        )
        records.append(record)

    out_path = PROCESSED_DIR / "migration-examples.jsonl"
    written = write_jsonl(records, out_path)
    console.print(f"[bold green]✓ {written} migration examples → {out_path.name}[/bold green]")
    console.print(f"\nPairs cover: declare_id→declare_program, coral-xyz→solana-foundation,")
    console.print(f"  manual validation→constraints, raw AccountInfo→typed wrappers,")
    console.print(f"  manual CPI→CpiContext, manual space→InitSpace, deprecated APIs")

    if written < count:
        console.print(f"\n[yellow]Generated {written}/{count} — add more pairs to MIGRATION_PAIRS or use synthetic.py for variations[/yellow]")


if __name__ == "__main__":
    app()
