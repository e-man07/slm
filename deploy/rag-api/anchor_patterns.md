# Anchor 0.32 — Verified Compilable Patterns Reference

## Program Declaration
```rust
use anchor_lang::prelude::*;
declare_id!("YourProgramId11111111111111111111111111111111");

#[program]
pub mod my_program {
    use super::*;
    // instructions here
}
```

## Account Init with Space Calculation
```rust
#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = signer, space = 8 + MyAccount::INIT_SPACE)]
    pub my_account: Account<'info, MyAccount>,
    #[account(mut)]
    pub signer: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct MyAccount {
    pub authority: Pubkey,       // 32 bytes
    pub count: u64,              // 8 bytes
    pub is_active: bool,         // 1 byte
    #[max_len(200)]
    pub name: String,            // 4 + 200 bytes
}
```

## PDA with Seeds and Bump
```rust
#[derive(Accounts)]
pub struct CreatePda<'info> {
    #[account(
        init,
        payer = user,
        space = 8 + Profile::INIT_SPACE,
        seeds = [b"profile", user.key().as_ref()],
        bump,
    )]
    pub profile: Account<'info, Profile>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

## PDA with Instruction Arguments in Seeds
```rust
#[derive(Accounts)]
#[instruction(price: u64)]
pub struct CreateListing<'info> {
    #[account(
        init,
        payer = seller,
        space = 8 + 32 + 8 + 1,
        seeds = [b"listing", seller.key().as_ref(), &price.to_le_bytes()],
        bump,
    )]
    pub listing: Account<'info, Listing>,
    #[account(mut)]
    pub seller: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

## has_one Constraint (field names must match exactly)
```rust
// The field name in the Account struct MUST match the field name in Accounts struct
#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut, has_one = authority)]  // checks vault.authority == authority.key()
    pub vault: Account<'info, Vault>,
    pub authority: Signer<'info>,         // field name MUST be "authority"
}

#[account]
pub struct Vault {
    pub authority: Pubkey,    // this field name must match
    pub balance: u64,
}
```

## Close Account (return rent to destination)
```rust
#[derive(Accounts)]
pub struct CloseMyAccount<'info> {
    #[account(mut, close = destination)]
    pub my_account: Account<'info, MyAccount>,
    #[account(mut)]
    pub destination: Signer<'info>,
}
```

## SOL Transfer via System Program CPI
```rust
use anchor_lang::system_program;

pub fn transfer_sol(ctx: Context<TransferSol>, amount: u64) -> Result<()> {
    system_program::transfer(
        CpiContext::new(
            ctx.accounts.system_program.to_account_info(),
            system_program::Transfer {
                from: ctx.accounts.sender.to_account_info(),
                to: ctx.accounts.recipient.to_account_info(),
            },
        ),
        amount,
    )
}

#[derive(Accounts)]
pub struct TransferSol<'info> {
    #[account(mut)]
    pub sender: Signer<'info>,
    /// CHECK: can be any account
    #[account(mut)]
    pub recipient: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}
```

## SPL Token Transfer
```rust
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

pub fn transfer_tokens(ctx: Context<TransferTokens>, amount: u64) -> Result<()> {
    token::transfer(
        CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.from_ata.to_account_info(),
                to: ctx.accounts.to_ata.to_account_info(),
                authority: ctx.accounts.authority.to_account_info(),
            },
        ),
        amount,
    )
}

#[derive(Accounts)]
pub struct TransferTokens<'info> {
    #[account(mut, token::authority = authority)]
    pub from_ata: Account<'info, TokenAccount>,
    #[account(mut)]
    pub to_ata: Account<'info, TokenAccount>,
    pub authority: Signer<'info>,
    pub token_program: Program<'info, Token>,
}
```

## SPL Token Mint To (PDA as mint authority)
```rust
use anchor_spl::token::{self, Token, Mint, TokenAccount, MintTo};

pub fn mint_tokens(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
    let seeds = &[b"mint_auth".as_ref(), &[ctx.bumps.mint_authority]];
    let signer_seeds = &[&seeds[..]];

    token::mint_to(
        CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            MintTo {
                mint: ctx.accounts.mint.to_account_info(),
                to: ctx.accounts.token_account.to_account_info(),
                authority: ctx.accounts.mint_authority.to_account_info(),
            },
            signer_seeds,
        ),
        amount,
    )
}

#[derive(Accounts)]
pub struct MintTokens<'info> {
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,
    /// CHECK: PDA used as mint authority
    #[account(seeds = [b"mint_auth"], bump)]
    pub mint_authority: UncheckedAccount<'info>,
    pub token_program: Program<'info, Token>,
}
```

## SPL Token Burn
```rust
use anchor_spl::token::{self, Token, Mint, TokenAccount, Burn};

pub fn burn_tokens(ctx: Context<BurnTokens>, amount: u64) -> Result<()> {
    token::burn(
        CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Burn {
                mint: ctx.accounts.mint.to_account_info(),
                from: ctx.accounts.token_account.to_account_info(),
                authority: ctx.accounts.authority.to_account_info(),
            },
        ),
        amount,
    )
}

#[derive(Accounts)]
pub struct BurnTokens<'info> {
    #[account(mut)]
    pub mint: Account<'info, Mint>,
    #[account(mut, token::mint = mint, token::authority = authority)]
    pub token_account: Account<'info, TokenAccount>,
    pub authority: Signer<'info>,
    pub token_program: Program<'info, Token>,
}
```

## Associated Token Account Init
```rust
use anchor_spl::{
    associated_token::AssociatedToken,
    token::{Token, Mint, TokenAccount},
};

#[derive(Accounts)]
pub struct CreateAta<'info> {
    #[account(
        init_if_needed,
        payer = payer,
        associated_token::mint = mint,
        associated_token::authority = owner,
    )]
    pub token_account: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    /// CHECK: token account owner
    pub owner: UncheckedAccount<'info>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
}
```

## Custom Errors
```rust
#[error_code]
pub enum MyError {
    #[msg("Value must be greater than zero")]
    ValueIsZero,
    #[msg("Unauthorized access")]
    Unauthorized,
    #[msg("Overflow occurred")]
    Overflow,
}

// Usage:
require!(amount > 0, MyError::ValueIsZero);
require_keys_eq!(ctx.accounts.authority.key(), vault.authority, MyError::Unauthorized);
```

## Events
```rust
#[event]
pub struct TransferEvent {
    pub from: Pubkey,
    pub to: Pubkey,
    pub amount: u64,
    pub timestamp: i64,
}

// Usage in instruction:
let clock = Clock::get()?;
emit!(TransferEvent {
    from: ctx.accounts.sender.key(),
    to: ctx.accounts.recipient.key(),
    amount,
    timestamp: clock.unix_timestamp,
});
```

## Clock Sysvar
```rust
pub fn check_time(ctx: Context<CheckTime>) -> Result<()> {
    let clock = Clock::get()?;
    let now = clock.unix_timestamp;
    require!(now >= ctx.accounts.vault.unlock_time, MyError::StillLocked);
    Ok(())
}
```

## Checked Arithmetic
```rust
// Always use checked math for user-provided values
let new_balance = vault.balance
    .checked_add(amount)
    .ok_or(MyError::Overflow)?;

let shares = deposit_amount
    .checked_mul(total_shares)
    .ok_or(MyError::Overflow)?
    .checked_div(pool_balance)
    .ok_or(MyError::Overflow)?;
```

## Avoiding Borrow Checker Issues
```rust
// WRONG — mutable + immutable borrow conflict:
pub fn release(ctx: Context<Release>) -> Result<()> {
    let escrow = &mut ctx.accounts.escrow;
    require_keys_eq!(escrow.sender, ctx.accounts.sender.key()); // immutable borrow
    escrow.is_released = true; // mutable borrow — CONFLICT
    Ok(())
}

// CORRECT — read into local variable first:
pub fn release(ctx: Context<Release>) -> Result<()> {
    let sender_key = ctx.accounts.escrow.sender;  // read first
    require_keys_eq!(sender_key, ctx.accounts.sender.key());
    ctx.accounts.escrow.is_released = true;  // now safe to mutate
    Ok(())
}
```

## Hardcoded Pubkey Constant
```rust
// Use exactly 32 bytes
const ADMIN: Pubkey = Pubkey::new_from_array([
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32,
]);
```

## Zero-Copy for Large Accounts
```rust
#[account(zero_copy)]
#[repr(C)]
pub struct LargeAccount {
    pub data: [u64; 1000],
}

#[derive(Accounts)]
pub struct UseLarge<'info> {
    #[account(mut)]
    pub large: AccountLoader<'info, LargeAccount>,
}

// Usage:
let mut account = ctx.accounts.large.load_mut()?;
account.data[0] = 42;
```

## Realloc (resize account)
```rust
#[derive(Accounts)]
pub struct Resize<'info> {
    #[account(
        mut,
        realloc = 8 + 4 + new_len,
        realloc::payer = payer,
        realloc::zero = false,
    )]
    pub data_account: Account<'info, DataAccount>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

## CPI with PDA Signer
```rust
pub fn cpi_transfer(ctx: Context<CpiTransfer>, amount: u64) -> Result<()> {
    let bump = ctx.bumps.vault;
    let seeds = &[b"vault".as_ref(), &[bump]];
    let signer_seeds = &[&seeds[..]];

    system_program::transfer(
        CpiContext::new_with_signer(
            ctx.accounts.system_program.to_account_info(),
            system_program::Transfer {
                from: ctx.accounts.vault.to_account_info(),
                to: ctx.accounts.recipient.to_account_info(),
            },
            signer_seeds,
        ),
        amount,
    )
}
```

## Access Control
```rust
#[access_control(check_admin(&ctx))]
pub fn admin_action(ctx: Context<AdminAction>) -> Result<()> {
    // only runs if check_admin passes
    Ok(())
}

fn check_admin(ctx: &Context<AdminAction>) -> Result<()> {
    require_keys_eq!(ctx.accounts.admin.key(), ADMIN_PUBKEY, MyError::Unauthorized);
    Ok(())
}
```

## Remaining Accounts
```rust
pub fn process_many(ctx: Context<ProcessMany>) -> Result<()> {
    for account_info in ctx.remaining_accounts.iter() {
        // process each additional account
        msg!("Processing: {}", account_info.key());
    }
    Ok(())
}
```
