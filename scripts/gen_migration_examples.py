#!/usr/bin/env python3
"""Generate additional Anchor migration examples (old -> new patterns).
Produces CPT + SFT records directly, appended to training data on container.
"""
import json
from pathlib import Path

SYSTEM_PROMPT = (
    "You are an expert Solana/Anchor developer specializing in helping "
    "developers migrate to modern Anchor 0.30+ patterns."
)

DATA_DIR = Path("/workspace/data")

# Additional migration pairs beyond the original 10
# Format: (description, old_code, new_code)
EXTRA_PAIRS = [
    # --- Account Init patterns ---
    (
        "Migrate manual account creation to Anchor init with InitSpace",
        '''// Old: manual system program invoke for account creation
let rent = Rent::get()?;
let space = 8 + 32 + 8;
let lamports = rent.minimum_balance(space);
let ix = system_instruction::create_account(
    ctx.accounts.payer.key,
    ctx.accounts.new_account.key,
    lamports, space as u64,
    ctx.program_id,
);
invoke(&ix, &[
    ctx.accounts.payer.to_account_info(),
    ctx.accounts.new_account.to_account_info(),
])?;''',
        '''// Modern: Anchor init constraint handles everything
#[derive(Accounts)]
pub struct Create<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,
    #[account(
        init,
        payer = payer,
        space = 8 + MyAccount::INIT_SPACE,
    )]
    pub new_account: Account<'info, MyAccount>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct MyAccount {
    pub authority: Pubkey,
    pub value: u64,
}''',
    ),
    # --- Token operations ---
    (
        "Migrate SPL token transfer from raw invoke to anchor_spl",
        '''// Old: raw spl_token invoke
use spl_token::instruction::transfer;
let ix = transfer(
    &spl_token::id(),
    source.key, dest.key, authority.key,
    &[], amount,
)?;
invoke(&ix, &[source.clone(), dest.clone(), authority.clone()])?;''',
        '''// Modern: anchor_spl::token::transfer
use anchor_spl::token::{self, Transfer, Token, TokenAccount};

let cpi_accounts = Transfer {
    from: ctx.accounts.source.to_account_info(),
    to: ctx.accounts.destination.to_account_info(),
    authority: ctx.accounts.authority.to_account_info(),
};
let cpi_ctx = CpiContext::new(
    ctx.accounts.token_program.to_account_info(),
    cpi_accounts,
);
token::transfer(cpi_ctx, amount)?;''',
    ),
    (
        "Migrate token mint from raw invoke to anchor_spl",
        '''// Old: raw spl_token mint_to invoke
let ix = spl_token::instruction::mint_to(
    &spl_token::id(),
    mint.key, account.key, authority.key,
    &[], amount,
)?;
invoke_signed(&ix, &[mint.clone(), account.clone(), authority.clone()], signer_seeds)?;''',
        '''// Modern: anchor_spl::token::mint_to
use anchor_spl::token::{self, MintTo};

let cpi_accounts = MintTo {
    mint: ctx.accounts.mint.to_account_info(),
    to: ctx.accounts.token_account.to_account_info(),
    authority: ctx.accounts.mint_authority.to_account_info(),
};
let cpi_ctx = CpiContext::new_with_signer(
    ctx.accounts.token_program.to_account_info(),
    cpi_accounts,
    signer_seeds,
);
token::mint_to(cpi_ctx, amount)?;''',
    ),
    (
        "Migrate token burn from raw invoke to anchor_spl",
        '''// Old: raw spl_token burn
let ix = spl_token::instruction::burn(
    &spl_token::id(),
    account.key, mint.key, authority.key,
    &[], amount,
)?;
invoke(&ix, &[account.clone(), mint.clone(), authority.clone()])?;''',
        '''// Modern: anchor_spl::token::burn
use anchor_spl::token::{self, Burn};

let cpi_accounts = Burn {
    mint: ctx.accounts.mint.to_account_info(),
    from: ctx.accounts.token_account.to_account_info(),
    authority: ctx.accounts.authority.to_account_info(),
};
token::burn(
    CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts),
    amount,
)?;''',
    ),
    # --- PDA patterns ---
    (
        "Migrate manual bump storage to ctx.bumps",
        '''// Old: store bump manually
let (pda, bump) = Pubkey::find_program_address(
    &[b"config", authority.key().as_ref()],
    program_id,
);
config.bump = bump;''',
        '''// Modern: ctx.bumps auto-provides the bump
#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = authority,
        space = 8 + Config::INIT_SPACE,
        seeds = [b"config", authority.key().as_ref()],
        bump,
    )]
    pub config: Account<'info, Config>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}

pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
    ctx.accounts.config.bump = ctx.bumps.config;
    Ok(())
}''',
    ),
    (
        "Migrate PDA signer seeds from manual to Anchor seeds constraint",
        '''// Old: manual PDA signing
let seeds = &[b"vault".as_ref(), &[vault_bump]];
let signer = &[&seeds[..]];
invoke_signed(&transfer_ix, accounts, signer)?;''',
        '''// Modern: Anchor handles PDA signing with seeds constraint
#[derive(Accounts)]
pub struct VaultTransfer<'info> {
    #[account(
        mut,
        seeds = [b"vault"],
        bump = vault.bump,
    )]
    pub vault: Account<'info, Vault>,
    // Anchor auto-generates signer seeds from the seeds constraint
}''',
    ),
    # --- Error handling ---
    (
        "Migrate ProgramError to Anchor error_code with require!",
        '''// Old: ProgramError with manual checks
if amount == 0 {
    return Err(ProgramError::InvalidArgument);
}
if ctx.accounts.user.balance < amount {
    return Err(ProgramError::InsufficientFunds);
}''',
        '''// Modern: Anchor require! macros with custom errors
require!(amount > 0, ErrorCode::InvalidAmount);
require_gte!(ctx.accounts.user.balance, amount, ErrorCode::InsufficientFunds);

#[error_code]
pub enum ErrorCode {
    #[msg("Amount must be greater than zero")]
    InvalidAmount,
    #[msg("Insufficient funds for this operation")]
    InsufficientFunds,
}''',
    ),
    (
        "Migrate require_keys_eq for ownership checks",
        '''// Old: manual key comparison
if ctx.accounts.vault.authority != ctx.accounts.signer.key() {
    return Err(ErrorCode::Unauthorized.into());
}''',
        '''// Modern: require_keys_eq! macro
require_keys_eq!(
    ctx.accounts.vault.authority,
    ctx.accounts.signer.key(),
    ErrorCode::Unauthorized
);''',
    ),
    # --- Associated token account ---
    (
        "Migrate ATA creation from manual to Anchor associated_token constraint",
        '''// Old: manual ATA creation via CPI
let create_ata_ix = spl_associated_token_account::instruction::create_associated_token_account(
    payer.key, wallet.key, mint.key, &spl_token::id(),
);
invoke(&create_ata_ix, &[payer.clone(), ata.clone(), wallet.clone(), mint.clone(), system.clone(), token.clone()])?;''',
        '''// Modern: Anchor associated_token constraint
#[derive(Accounts)]
pub struct CreateATA<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,
    pub wallet: SystemAccount<'info>,
    pub mint: Account<'info, Mint>,
    #[account(
        init_if_needed,
        payer = payer,
        associated_token::mint = mint,
        associated_token::authority = wallet,
    )]
    pub token_account: Account<'info, TokenAccount>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
}''',
    ),
    # --- Realloc ---
    (
        "Migrate manual realloc to Anchor realloc constraint",
        '''// Old: manual account realloc
let new_size = 8 + 32 + 4 + new_data.len();
let rent = Rent::get()?;
let new_minimum = rent.minimum_balance(new_size);
let diff = new_minimum.saturating_sub(account.lamports());
if diff > 0 {
    invoke(
        &system_instruction::transfer(payer.key, account.key, diff),
        &[payer.clone(), account.clone(), system.clone()],
    )?;
}
account.realloc(new_size, false)?;''',
        '''// Modern: Anchor realloc constraint
#[derive(Accounts)]
pub struct Resize<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,
    #[account(
        mut,
        realloc = 8 + 32 + 4 + new_len,
        realloc::payer = payer,
        realloc::zero = false,
    )]
    pub data_account: Account<'info, DataAccount>,
    pub system_program: Program<'info, System>,
}''',
    ),
    # --- Event emission ---
    (
        "Migrate sol_log to Anchor emit! event macro",
        '''// Old: manual log messages
msg!("Transfer completed: {} tokens from {} to {}", amount, from, to);
sol_log_compute_units();''',
        '''// Modern: Anchor typed events
#[event]
pub struct TransferEvent {
    pub from: Pubkey,
    pub to: Pubkey,
    pub amount: u64,
    pub timestamp: i64,
}

emit!(TransferEvent {
    from: ctx.accounts.from.key(),
    to: ctx.accounts.to.key(),
    amount,
    timestamp: Clock::get()?.unix_timestamp,
});''',
    ),
    # --- Access control ---
    (
        "Migrate manual admin check to Anchor access_control",
        '''// Old: manual admin check in function body
pub fn admin_action(ctx: Context<AdminAction>) -> Result<()> {
    if ctx.accounts.admin.key() != ADMIN_PUBKEY {
        return Err(ErrorCode::NotAdmin.into());
    }
    // ... action
    Ok(())
}''',
        '''// Modern: Anchor has_one + constraint
#[derive(Accounts)]
pub struct AdminAction<'info> {
    #[account(
        has_one = admin @ ErrorCode::NotAdmin,
    )]
    pub config: Account<'info, Config>,
    pub admin: Signer<'info>,
}

pub fn admin_action(ctx: Context<AdminAction>) -> Result<()> {
    // Validation already done by has_one constraint
    // ... action
    Ok(())
}''',
    ),
    # --- Program derived addresses with multiple seeds ---
    (
        "Migrate complex PDA with multiple seeds",
        '''// Old: manual multi-seed PDA
let (vault_pda, vault_bump) = Pubkey::find_program_address(
    &[
        b"vault",
        pool.key().as_ref(),
        mint.key().as_ref(),
        &pool.vault_count.to_le_bytes(),
    ],
    program_id,
);
require_keys_eq!(vault_account.key(), vault_pda);''',
        '''// Modern: Anchor seeds constraint with multiple seeds
#[derive(Accounts)]
pub struct CreateVault<'info> {
    pub pool: Account<'info, Pool>,
    pub mint: Account<'info, Mint>,
    #[account(
        init,
        payer = authority,
        space = 8 + Vault::INIT_SPACE,
        seeds = [
            b"vault",
            pool.key().as_ref(),
            mint.key().as_ref(),
            &pool.vault_count.to_le_bytes(),
        ],
        bump,
    )]
    pub vault: Account<'info, Vault>,
    #[account(mut)]
    pub authority: Signer<'info>,
    pub system_program: Program<'info, System>,
}''',
    ),
    # --- Token-2022 / Token Extensions ---
    (
        "Migrate from spl-token to Token-2022 extensions",
        '''// Old: basic spl-token
use anchor_spl::token::{Token, TokenAccount, Mint};

#[derive(Accounts)]
pub struct TokenOp<'info> {
    pub token_program: Program<'info, Token>,
    pub mint: Account<'info, Mint>,
    pub token_account: Account<'info, TokenAccount>,
}''',
        '''// Modern: Token-2022 with extensions support
use anchor_spl::token_2022::Token2022;
use anchor_spl::token_interface::{TokenAccount, Mint, TokenInterface};

#[derive(Accounts)]
pub struct TokenOp<'info> {
    pub token_program: Interface<'info, TokenInterface>,
    pub mint: InterfaceAccount<'info, Mint>,
    pub token_account: InterfaceAccount<'info, TokenAccount>,
}
// TokenInterface works with both Token and Token-2022 programs''',
    ),
    # --- Remaining accounts pattern ---
    (
        "Migrate dynamic accounts from AccountInfo vec to remaining_accounts",
        '''// Old: pass arbitrary AccountInfo vec
pub fn process_many(ctx: Context<ProcessMany>, data: Vec<u8>) -> Result<()> {
    for account in ctx.accounts.accounts.iter() {
        // Unsafe: no type checking
        let info = account.to_account_info();
        // ...
    }
    Ok(())
}''',
        '''// Modern: use remaining_accounts with proper deserialization
pub fn process_many(ctx: Context<ProcessMany>, data: Vec<u8>) -> Result<()> {
    for account_info in ctx.remaining_accounts.iter() {
        let account: Account<MyAccount> = Account::try_from(account_info)?;
        // Type-safe access
        msg!("Processing account: {}", account.key());
    }
    Ok(())
}''',
    ),
    # --- Sysvar access ---
    (
        "Migrate sysvar from AccountInfo to Sysvar type",
        '''// Old: manual sysvar deserialization
/// CHECK: verified as Clock sysvar
pub clock: AccountInfo<'info>,

let clock = Clock::from_account_info(&ctx.accounts.clock)?;
let timestamp = clock.unix_timestamp;''',
        '''// Modern: use Clock::get() directly (no account needed)
pub fn my_instruction(ctx: Context<MyCtx>) -> Result<()> {
    let timestamp = Clock::get()?.unix_timestamp;
    let slot = Clock::get()?.slot;
    let rent = Rent::get()?;
    // No need to pass sysvar accounts anymore
    Ok(())
}''',
    ),
    # --- Zero-copy accounts ---
    (
        "Migrate large account to zero-copy for performance",
        '''// Old: standard borsh deserialization (copies entire account into memory)
#[account]
pub struct LargeData {
    pub entries: Vec<DataEntry>,  // Deserializes entire vec on every access
}''',
        '''// Modern: zero-copy for large accounts (10KB+ accounts)
#[account(zero_copy)]
#[repr(C)]
pub struct LargeData {
    pub count: u32,
    pub entries: [DataEntry; 256],  // Fixed-size, memory-mapped
}

#[derive(Accounts)]
pub struct AccessLargeData<'info> {
    #[account(mut)]
    pub data: AccountLoader<'info, LargeData>,  // AccountLoader for zero-copy
}

pub fn update(ctx: Context<AccessLargeData>) -> Result<()> {
    let mut data = ctx.accounts.data.load_mut()?;
    data.entries[0].value = 42;
    Ok(())
}''',
    ),
    # --- Composability ---
    (
        "Migrate hardcoded program ID to Interface for composability",
        '''// Old: hardcoded program ID check
pub fn swap(ctx: Context<Swap>) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.dex_program.key(),
        pubkey!("whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"),
    );
    // CPI to specific DEX
}''',
        '''// Modern: use Interface for composable CPI
use anchor_lang::prelude::*;

#[derive(Accounts)]
pub struct Swap<'info> {
    /// Accepts any program that implements the swap interface
    pub dex_program: Interface<'info, DexInterface>,
}

// Define interface - works with Orca, Raydium, Jupiter, etc.
pub trait DexInterface {}''',
    ),
    # --- Constraint expressions ---
    (
        "Migrate if-else validation to constraint expressions",
        '''// Old: verbose if-else chain
pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
    if amount == 0 {
        return Err(ErrorCode::ZeroAmount.into());
    }
    if amount > MAX_DEPOSIT {
        return Err(ErrorCode::ExceedsMax.into());
    }
    if ctx.accounts.pool.is_paused {
        return Err(ErrorCode::PoolPaused.into());
    }
    if Clock::get()?.unix_timestamp > ctx.accounts.pool.deadline {
        return Err(ErrorCode::DeadlinePassed.into());
    }
    // deposit logic...
    Ok(())
}''',
        '''// Modern: Anchor constraints on accounts struct
#[derive(Accounts)]
pub struct Deposit<'info> {
    #[account(
        mut,
        constraint = !pool.is_paused @ ErrorCode::PoolPaused,
        constraint = Clock::get()?.unix_timestamp <= pool.deadline @ ErrorCode::DeadlinePassed,
    )]
    pub pool: Account<'info, Pool>,
    #[account(mut)]
    pub depositor: Signer<'info>,
}

pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
    require!(amount > 0, ErrorCode::ZeroAmount);
    require_gte!(MAX_DEPOSIT, amount, ErrorCode::ExceedsMax);
    // Pool validation already handled by constraints
    // deposit logic...
    Ok(())
}''',
    ),
    # --- Anchor IDL generation ---
    (
        "Migrate manual IDL to Anchor auto-generated IDL",
        '''// Old: manually written IDL JSON
{
  "version": "0.1.0",
  "name": "my_program",
  "instructions": [{
    "name": "initialize",
    "accounts": [
      {"name": "user", "isMut": true, "isSigner": true}
    ],
    "args": [{"name": "data", "type": "string"}]
  }]
}''',
        '''// Modern: Anchor auto-generates IDL from code
// Just define your program normally:
#[program]
pub mod my_program {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, data: String) -> Result<()> {
        ctx.accounts.user_data.data = data;
        Ok(())
    }
}

// Build with: anchor build
// IDL auto-generated at target/idl/my_program.json
// TypeScript types at target/types/my_program.ts
// Fetch on-chain: anchor idl fetch <PROGRAM_ID>''',
    ),
]


def main():
    cpt_records = []
    sft_records = []

    for desc, old_code, new_code in EXTRA_PAIRS:
        question = f"How do I migrate this old Anchor/Solana code to modern patterns?\n\n```rust\n{old_code.strip()}\n```"
        answer = (
            f"Here's the migration to modern Anchor 0.30+ patterns ({desc}):\n\n"
            f"```rust\n{new_code.strip()}\n```\n\n"
            f"Key changes:\n"
            f"- Uses modern Anchor 0.30+ conventions from solana-foundation/anchor\n"
            f"- Leverages Anchor's built-in constraint system for validation\n"
            f"- Reduces manual boilerplate and improves safety"
        )

        cpt_records.append({"text": f"Question: {question}\n\nAnswer: {answer}"})
        sft_records.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        })

    # Append to existing data
    cpt_path = DATA_DIR / "cpt_train.jsonl"
    sft_path = DATA_DIR / "sft_train.jsonl"

    with open(cpt_path, "a") as f:
        for rec in cpt_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with open(sft_path, "a") as f:
        for rec in sft_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Added {len(cpt_records)} migration CPT records")
    print(f"Added {len(sft_records)} migration SFT records")
    print(f"Total migration examples: {10 + len(EXTRA_PAIRS)} (10 original + {len(EXTRA_PAIRS)} new)")

    # Final counts
    cpt_total = sum(1 for _ in open(cpt_path))
    sft_total = sum(1 for _ in open(sft_path))
    print(f"\nFinal CPT: {cpt_total:,} records")
    print(f"Final SFT: {sft_total:,} records")


if __name__ == "__main__":
    main()
