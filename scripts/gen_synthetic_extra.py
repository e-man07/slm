#!/usr/bin/env python3
"""Additional synthetic training data — GLAN batch (DeFi, security, advanced patterns)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from schema import Record, write_jsonl

SYSTEM = "You are an expert Solana and Anchor developer. Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns."
OUT_DIR = Path(__file__).parent.parent / "data" / "processed"

def m(u, a):
    return json.dumps([{"role":"system","content":SYSTEM},{"role":"user","content":u},{"role":"assistant","content":a}], ensure_ascii=False)

def rec(content, method, category=""):
    meta = {"method": method, "collected_at": "2026-03-27"}
    if category: meta["category"] = category
    return Record(id=Record.make_id(content), source=f"synthetic/{method}", source_type="qa", content=content, language="rust", license="synthetic-claude", metadata=meta)

GLAN = []

# ── PDA Advanced ──────────────────────────────────────────────────────────

GLAN.append(("pda", m(
    "How do I derive a PDA with multiple seeds including a u64?",
    """```rust
#[derive(Accounts)]
pub struct CreateOrder<'info> {
    #[account(
        init, payer = user,
        space = 8 + Order::INIT_SPACE,
        seeds = [b"order", user.key().as_ref(), &order_id.to_le_bytes()],
        bump,
    )]
    pub order: Account<'info, Order>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```
Convert `u64` to bytes with `.to_le_bytes()`. The PDA is unique per user + order_id combination.""")))

GLAN.append(("pda", m(
    "How do I use a string as a PDA seed in Anchor?",
    """```rust
#[derive(Accounts)]
#[instruction(name: String)]
pub struct CreateProfile<'info> {
    #[account(
        init, payer = user,
        space = 8 + Profile::INIT_SPACE,
        seeds = [b"profile", name.as_bytes()],
        bump,
    )]
    pub profile: Account<'info, Profile>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```
Use `#[instruction(name: String)]` to access instruction args in seeds. Use `.as_bytes()` for string seeds. Be aware: different strings = different PDAs, so normalize (e.g., lowercase) before deriving if needed.""")))

GLAN.append(("pda", m(
    "How does a PDA sign a CPI in Anchor?",
    """```rust
pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
    let bump = ctx.bumps.vault;
    let seeds: &[&[u8]] = &[b"vault", ctx.accounts.authority.key.as_ref(), &[bump]];
    let signer_seeds = &[seeds];

    token::transfer(
        CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.vault_token.to_account_info(),
                to: ctx.accounts.user_token.to_account_info(),
                authority: ctx.accounts.vault.to_account_info(),
            },
            signer_seeds,
        ),
        amount,
    )
}
```
Use `CpiContext::new_with_signer` with the PDA's seeds + bump. The runtime verifies the seeds derive to the PDA's address.""")))

GLAN.append(("pda", m(
    "What's the difference between find_program_address and create_program_address?",
    """`Pubkey::find_program_address(seeds, program_id)` iterates bumps from 255 down to find the first valid PDA (canonical bump). It returns `(pubkey, bump)`.

`Pubkey::create_program_address(seeds_with_bump, program_id)` tries a specific bump — returns `Ok(pubkey)` or `Err` if the bump produces a point on the Ed25519 curve.

**Always use `find_program_address`** (or Anchor's `seeds` + `bump` constraint which does this automatically). Store the canonical bump in the account to avoid re-deriving:

```rust
#[account(seeds = [b"config"], bump = config.bump)]  // uses stored bump, saves ~1500 CU
pub config: Account<'info, Config>,
```

Never use a non-canonical bump — it's a security risk (attacker could use a different bump to derive a different address).""")))

GLAN.append(("pda", m(
    "How do I derive a PDA in TypeScript that matches Anchor's derivation?",
    """```typescript
import { PublicKey } from "@solana/web3.js";

// Must match the seeds in your Anchor program exactly
const [pda, bump] = PublicKey.findProgramAddressSync(
  [
    Buffer.from("vault"),
    userPubkey.toBuffer(),
    new anchor.BN(orderId).toArrayLike(Buffer, "le", 8), // u64 little-endian
  ],
  programId,
);

// For string seeds:
const [profilePda] = PublicKey.findProgramAddressSync(
  [Buffer.from("profile"), Buffer.from(username)],
  programId,
);
```
Seed order and encoding must exactly match the on-chain program. Use `"le"` (little-endian) for numeric seeds to match Rust's `.to_le_bytes()`.""")))

# ── DeFi Patterns ─────────────────────────────────────────────────────────

GLAN.append(("defi", m(
    "How do I implement a constant product AMM swap in Anchor?",
    """```rust
pub fn swap(ctx: Context<Swap>, amount_in: u64, min_out: u64) -> Result<()> {
    let reserve_a = ctx.accounts.pool_token_a.amount;
    let reserve_b = ctx.accounts.pool_token_b.amount;

    // x * y = k (constant product)
    // amount_out = (reserve_b * amount_in) / (reserve_a + amount_in)
    let numerator = (reserve_b as u128).checked_mul(amount_in as u128).ok_or(AmmError::Overflow)?;
    let denominator = (reserve_a as u128).checked_add(amount_in as u128).ok_or(AmmError::Overflow)?;
    let amount_out = (numerator / denominator) as u64;

    require!(amount_out >= min_out, AmmError::SlippageExceeded);

    // Transfer in from user
    token::transfer(CpiContext::new(/*...*/), amount_in)?;
    // Transfer out to user (PDA signer)
    token::transfer(CpiContext::new_with_signer(/*...*/), amount_out)?;

    Ok(())
}

#[error_code]
pub enum AmmError {
    #[msg("Output below minimum")] SlippageExceeded,
    #[msg("Math overflow")] Overflow,
}
```
Use `u128` for intermediate math to prevent overflow. Always enforce `min_out` for slippage protection.""")))

GLAN.append(("defi", m(
    "How do I implement add/remove liquidity for an AMM pool?",
    """```rust
pub fn add_liquidity(ctx: Context<AddLiquidity>, amount_a: u64, amount_b: u64) -> Result<()> {
    let pool = &mut ctx.accounts.pool;
    let lp_to_mint: u64;

    if pool.total_lp == 0 {
        // First deposit: LP = sqrt(amount_a * amount_b)
        lp_to_mint = (amount_a as f64 * amount_b as f64).sqrt() as u64;
    } else {
        // Proportional: LP = min(a/reserve_a, b/reserve_b) * total_lp
        let ratio_a = (amount_a as u128) * (pool.total_lp as u128) / (pool.reserve_a as u128);
        let ratio_b = (amount_b as u128) * (pool.total_lp as u128) / (pool.reserve_b as u128);
        lp_to_mint = ratio_a.min(ratio_b) as u64;
    }

    require!(lp_to_mint > 0, AmmError::ZeroLp);

    // Transfer both tokens into pool, mint LP tokens to user
    token::transfer(/*..token A..*/)?;
    token::transfer(/*..token B..*/)?;
    token::mint_to(/*..LP mint with PDA signer..*/)?;

    pool.reserve_a += amount_a;
    pool.reserve_b += amount_b;
    pool.total_lp += lp_to_mint;
    Ok(())
}

pub fn remove_liquidity(ctx: Context<RemoveLiquidity>, lp_amount: u64) -> Result<()> {
    let pool = &mut ctx.accounts.pool;
    let share = lp_amount as u128;
    let total = pool.total_lp as u128;

    let amount_a = (share * pool.reserve_a as u128 / total) as u64;
    let amount_b = (share * pool.reserve_b as u128 / total) as u64;

    // Burn LP, transfer tokens back to user
    token::burn(/*..*/)?;
    token::transfer(/*..PDA signer, token A..*/)?;
    token::transfer(/*..PDA signer, token B..*/)?;

    pool.reserve_a -= amount_a;
    pool.reserve_b -= amount_b;
    pool.total_lp -= lp_amount;
    Ok(())
}
```
LP tokens represent proportional pool ownership. First depositor sets the ratio.""")))

GLAN.append(("defi", m(
    "How do I implement a flash loan in Anchor?",
    """```rust
pub fn flash_loan(ctx: Context<FlashLoan>, amount: u64) -> Result<()> {
    let vault_balance_before = ctx.accounts.vault.amount;

    // Transfer tokens to borrower
    let seeds = &[b"vault".as_ref(), &[ctx.bumps.vault]];
    token::transfer(
        CpiContext::new_with_signer(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.vault.to_account_info(),
                to: ctx.accounts.borrower_token.to_account_info(),
                authority: ctx.accounts.vault.to_account_info() },
            &[seeds]),
        amount)?;

    // Borrower executes their logic via CPI (remaining_accounts)
    // ...

    // Reload account data after CPI
    ctx.accounts.vault.reload()?;
    let vault_balance_after = ctx.accounts.vault.amount;

    // Fee: 0.09% (9 basis points)
    let fee = amount.checked_mul(9).unwrap().checked_div(10000).unwrap();
    let required = vault_balance_before.checked_add(fee).ok_or(FlashError::Overflow)?;

    require!(vault_balance_after >= required, FlashError::NotRepaid);
    Ok(())
}

#[error_code]
pub enum FlashError {
    #[msg("Flash loan not repaid with fee")] NotRepaid,
    #[msg("Overflow")] Overflow,
}
```
Key: use `.reload()?` to refresh account data after CPI, then verify the vault has been repaid with fee. The borrower must repay within the same transaction.""")))

GLAN.append(("defi", m(
    "How do I implement a lending deposit with collateral tracking?",
    """```rust
pub fn deposit_collateral(ctx: Context<DepositCollateral>, amount: u64) -> Result<()> {
    require!(amount > 0, LendError::ZeroAmount);

    token::transfer(
        CpiContext::new(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.user_token.to_account_info(),
                to: ctx.accounts.collateral_vault.to_account_info(),
                authority: ctx.accounts.user.to_account_info() }),
        amount)?;

    let position = &mut ctx.accounts.position;
    position.owner = ctx.accounts.user.key();
    position.collateral_amount = position.collateral_amount.checked_add(amount).ok_or(LendError::Overflow)?;
    position.collateral_mint = ctx.accounts.collateral_mint.key();
    position.bump = ctx.bumps.position;
    Ok(())
}

pub fn borrow(ctx: Context<Borrow>, borrow_amount: u64) -> Result<()> {
    let position = &mut ctx.accounts.position;

    // Health factor = (collateral_value * LTV) / (borrowed_value)
    // LTV = 75% for this example
    let max_borrow = position.collateral_amount.checked_mul(75).unwrap() / 100;
    let total_borrowed = position.borrowed_amount.checked_add(borrow_amount).ok_or(LendError::Overflow)?;
    require!(total_borrowed <= max_borrow, LendError::Undercollateralized);

    // Transfer borrowed tokens from lending pool to user (PDA signer)
    // ...

    position.borrowed_amount = total_borrowed;
    Ok(())
}

#[error_code]
pub enum LendError {
    #[msg("Zero")] ZeroAmount,
    #[msg("Undercollateralized")] Undercollateralized,
    #[msg("Overflow")] Overflow,
}
```
In production, use oracle prices (Pyth/Switchboard) instead of 1:1 collateral ratio.""")))

GLAN.append(("defi", m(
    "How do I implement liquidation in a lending protocol?",
    """```rust
pub fn liquidate(ctx: Context<Liquidate>, repay_amount: u64) -> Result<()> {
    let position = &ctx.accounts.position;

    // Check position is liquidatable (health factor < 1.0)
    // health = collateral_value * liquidation_threshold / borrowed_value
    let health_num = (position.collateral_amount as u128) * 80; // 80% threshold
    let health_den = (position.borrowed_amount as u128) * 100;
    require!(health_num < health_den, LiqError::Healthy);

    // Liquidator repays part of the debt
    require!(repay_amount <= position.borrowed_amount / 2, LiqError::TooMuch); // max 50%

    // Transfer repayment from liquidator to lending pool
    token::transfer(CpiContext::new(/*...*/), repay_amount)?;

    // Calculate collateral bonus (5% liquidation incentive)
    let collateral_to_seize = repay_amount * 105 / 100;

    // Transfer collateral to liquidator (PDA signer)
    token::transfer(CpiContext::new_with_signer(/*...*/), collateral_to_seize)?;

    // Update position
    let pos = &mut ctx.accounts.position;
    pos.borrowed_amount -= repay_amount;
    pos.collateral_amount -= collateral_to_seize;

    Ok(())
}

#[error_code]
pub enum LiqError {
    #[msg("Position is healthy")] Healthy,
    #[msg("Cannot liquidate more than 50%")] TooMuch,
}
```
Liquidation incentive (5% bonus collateral) motivates liquidators to keep the protocol solvent.""")))

GLAN.append(("defi", m(
    "How do I implement a simple order book in Anchor?",
    """```rust
#[account]
#[derive(InitSpace)]
pub struct Order {
    pub maker: Pubkey,
    pub price: u64,       // price in quote tokens per base token (scaled by 1e6)
    pub amount: u64,      // base token amount remaining
    pub side: u8,         // 0 = buy, 1 = sell
    pub timestamp: i64,
    pub bump: u8,
}

pub fn place_order(ctx: Context<PlaceOrder>, price: u64, amount: u64, side: u8) -> Result<()> {
    let clock = Clock::get()?;
    let order = &mut ctx.accounts.order;
    order.maker = ctx.accounts.maker.key();
    order.price = price;
    order.amount = amount;
    order.side = side;
    order.timestamp = clock.unix_timestamp;
    order.bump = ctx.bumps.order;

    // Escrow tokens from maker
    if side == 1 { // sell: escrow base tokens
        token::transfer(CpiContext::new(/*...*/), amount)?;
    } else { // buy: escrow quote tokens
        let quote_amount = (amount as u128 * price as u128 / 1_000_000) as u64;
        token::transfer(CpiContext::new(/*...*/), quote_amount)?;
    }
    Ok(())
}

pub fn fill_order(ctx: Context<FillOrder>, fill_amount: u64) -> Result<()> {
    let order = &mut ctx.accounts.order;
    require!(fill_amount <= order.amount, BookError::TooMuch);

    let quote_amount = (fill_amount as u128 * order.price as u128 / 1_000_000) as u64;

    // Swap: taker sends one side, receives other (PDA signer for escrow release)
    // ... token transfers ...

    order.amount -= fill_amount;
    Ok(())
}
```
Real order books (like OpenBook/Phoenix) use more efficient data structures, but this shows the pattern.""")))

GLAN.append(("defi", m(
    "How do I collect protocol fees in an Anchor DeFi program?",
    """```rust
#[account]
#[derive(InitSpace)]
pub struct ProtocolConfig {
    pub admin: Pubkey,
    pub fee_bps: u16,        // basis points (e.g., 30 = 0.3%)
    pub fee_vault: Pubkey,
    pub total_fees: u64,
    pub bump: u8,
}

pub fn swap_with_fee(ctx: Context<SwapWithFee>, amount_in: u64, min_out: u64) -> Result<()> {
    let config = &ctx.accounts.config;
    let fee = amount_in.checked_mul(config.fee_bps as u64).unwrap() / 10_000;
    let net_in = amount_in - fee;

    // Calculate output from net_in (after fee)
    let amount_out = calculate_output(net_in, reserve_a, reserve_b)?;
    require!(amount_out >= min_out, SwapError::Slippage);

    // Transfer fee to protocol vault
    token::transfer(CpiContext::new(/*...*/), fee)?;
    // Transfer net amount to pool
    token::transfer(CpiContext::new(/*...*/), net_in)?;
    // Transfer output to user
    token::transfer(CpiContext::new_with_signer(/*...*/), amount_out)?;

    ctx.accounts.config.total_fees += fee;
    Ok(())
}

pub fn update_fee(ctx: Context<AdminOnly>, new_fee_bps: u16) -> Result<()> {
    require!(new_fee_bps <= 1000, SwapError::FeeTooHigh); // max 10%
    ctx.accounts.config.fee_bps = new_fee_bps;
    Ok(())
}
```
Take fees BEFORE the swap calculation. Cap max fee to prevent admin abuse.""")))

# ── Security Patterns ─────────────────────────────────────────────────────

GLAN.append(("security", m(
    "How do I prevent type cosplay attacks in Anchor?",
    """Type cosplay = an attacker passes an account of the wrong type that happens to have valid data layout.

Anchor prevents this automatically with **8-byte discriminators** — each `#[account]` type gets a unique hash prefix. When you use `Account<'info, MyType>`, Anchor checks the first 8 bytes match `MyType`'s discriminator.

**You're vulnerable if you use:**
```rust
// BAD: no type checking
pub data: UncheckedAccount<'info>,

// Also risky: AccountInfo has no type validation
pub data: AccountInfo<'info>,
```

**Safe patterns:**
```rust
// GOOD: Anchor validates discriminator automatically
pub data: Account<'info, MySpecificType>,

// If you MUST use UncheckedAccount, add CHECK comment and validate manually:
/// CHECK: Validated in instruction logic via discriminator check
#[account(constraint = validate_account(&data) @ MyError::InvalidAccount)]
pub data: UncheckedAccount<'info>,
```

Never deserialize an `UncheckedAccount` without verifying its discriminator and owner first.""")))

GLAN.append(("security", m(
    "How do I prevent unauthorized account modification in Anchor?",
    """Three layers of protection:

**1. Ownership check (automatic):** `Account<'info, T>` verifies the account is owned by your program.

**2. Authority check via has_one:**
```rust
#[account(mut, has_one = authority @ MyError::Unauthorized)]
pub state: Account<'info, State>,
pub authority: Signer<'info>,  // must sign the tx
```

**3. PDA validation (strongest):**
```rust
#[account(
    mut,
    seeds = [b"state", authority.key().as_ref()],
    bump = state.bump,
    has_one = authority,
)]
pub state: Account<'info, State>,
pub authority: Signer<'info>,
```

**Common mistake — missing Signer:**
```rust
// BAD: anyone can pass any pubkey as authority
pub authority: AccountInfo<'info>,

// GOOD: requires actual signature
pub authority: Signer<'info>,
```

Always use `Signer<'info>` for authority accounts, not `AccountInfo` or `UncheckedAccount`.""")))

GLAN.append(("security", m(
    "How do I safely handle arithmetic in Solana programs?",
    """Rust integers panic on overflow in debug mode but **wrap silently in release mode** (which is what Solana uses). Always use checked math:

```rust
// BAD: silent overflow in release
let total = amount_a + amount_b;

// GOOD: returns None on overflow
let total = amount_a.checked_add(amount_b).ok_or(MyError::Overflow)?;

// GOOD: checked chain
let result = amount
    .checked_mul(price)?
    .checked_div(1_000_000)?;

// GOOD: for complex math, use u128 intermediates
let product = (amount as u128)
    .checked_mul(price as u128)
    .ok_or(MyError::Overflow)?;
let result = (product / 1_000_000) as u64;

// GOOD: Anchor's require! for bounds
require!(amount <= MAX_AMOUNT, MyError::TooLarge);
```

For DeFi, also watch for:
- **Division truncation**: `7 / 2 = 3` not 3.5. Round up when charging fees: `(amount * fee + 9999) / 10000`
- **Dust amounts**: Check `result > 0` after division
- **Sandwich attacks**: Always enforce `min_out` / `max_in` slippage bounds""")))

GLAN.append(("security", m(
    "How do I validate that a token account belongs to the right mint and owner?",
    """Use Anchor's token constraints:

```rust
#[derive(Accounts)]
pub struct SecureTransfer<'info> {
    // Validates mint AND authority in one line
    #[account(
        mut,
        token::mint = expected_mint,
        token::authority = user,
    )]
    pub user_token: Account<'info, TokenAccount>,

    // For ATAs, even stronger:
    #[account(
        mut,
        associated_token::mint = expected_mint,
        associated_token::authority = user,
    )]
    pub user_ata: Account<'info, TokenAccount>,

    pub expected_mint: Account<'info, Mint>,
    pub user: Signer<'info>,
}
```

**Without constraints (manual validation):**
```rust
require!(user_token.mint == expected_mint.key(), MyError::WrongMint);
require!(user_token.owner == user.key(), MyError::WrongOwner);
```

Never trust that a passed-in token account is correct without validation — attackers can pass any token account they own.""")))

GLAN.append(("security", m(
    "What is the missing signer check vulnerability?",
    """If you accept an authority as `AccountInfo` instead of `Signer`, anyone can impersonate them:

```rust
// VULNERABLE:
#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut, has_one = authority)]
    pub vault: Account<'info, Vault>,
    /// CHECK: NO SIGNER CHECK — ANYONE CAN PASS ANY PUBKEY
    pub authority: AccountInfo<'info>,  // BUG!
}

// FIXED:
#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut, has_one = authority)]
    pub vault: Account<'info, Vault>,
    pub authority: Signer<'info>,  // Must actually sign the transaction
}
```

`has_one = authority` only checks that `vault.authority == authority.key()`. It does NOT check that `authority` signed the transaction. You need `Signer<'info>` for that.

**Rule: Any account that authorizes an action must be `Signer<'info>`.**""")))

# ── Account Lifecycle ─────────────────────────────────────────────────────

GLAN.append(("accounts", m(
    "How do I resize an account with realloc in Anchor?",
    """```rust
#[derive(Accounts)]
#[instruction(new_data: Vec<u8>)]
pub struct ResizeAccount<'info> {
    #[account(
        mut,
        realloc = 8 + 32 + 4 + new_data.len(),  // discriminator + pubkey + vec_prefix + data
        realloc::payer = payer,
        realloc::zero = false,  // don't zero new space (saves CU)
        has_one = authority,
    )]
    pub data_account: Account<'info, DynamicData>,
    pub authority: Signer<'info>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

If the account grows, `payer` provides additional rent. If it shrinks, excess rent goes back to `payer`. Set `realloc::zero = true` if you need new bytes zeroed (slightly more expensive).

**Max account size is 10MB.** For data beyond that, use multiple accounts or compression.""")))

GLAN.append(("accounts", m(
    "How do I prevent account resurrection after closing?",
    """Anchor's `close` constraint sets the discriminator to a special "closed" marker. If someone sends lamports back to the address, Anchor will reject it because the discriminator doesn't match.

```rust
// Safe: Anchor handles everything
#[account(mut, close = recipient, has_one = authority)]
pub closeable: Account<'info, MyData>,

// The close constraint:
// 1. Transfers all lamports to recipient
// 2. Zeros account data
// 3. Sets discriminator to CLOSED_ACCOUNT_DISCRIMINATOR
// 4. Assigns owner back to System Program
```

**Old vulnerability (fixed years ago):** Before Anchor added the closed discriminator, attackers could:
1. Close an account
2. Send lamports back to make it rent-exempt
3. Re-use the stale data

This is **no longer an issue** with modern Anchor. The discriminator check prevents deserialization of closed accounts.""")))

GLAN.append(("accounts", m(
    "What's the maximum account size and how do I handle large data?",
    """Max account size is **10,237,952 bytes (~10MB)**.

For large data:

**1. Zero-copy (up to 10MB):**
```rust
#[account(zero_copy)]
#[repr(C)]
pub struct BigMap {
    pub entries: [Entry; 10000],  // fixed-size array
    pub count: u32,
}
```

**2. Multiple accounts (unlimited):**
```rust
#[account]
pub struct DataPage {
    pub parent: Pubkey,
    pub page_index: u32,
    pub data: [u8; 9000],
    pub next_page: Option<Pubkey>,
}
```

**3. Account compression (for NFTs):**
Use Metaplex Bubblegum for compressed NFTs — stores millions of NFTs in a single Merkle tree account.

**4. Off-chain + hash:**
Store data off-chain (Arweave, IPFS), keep only the hash on-chain:
```rust
#[account]
pub struct Reference {
    pub data_hash: [u8; 32],  // SHA256 of off-chain data
    pub uri: String,           // where to find it
}
```""")))

# ── Production Patterns ───────────────────────────────────────────────────

GLAN.append(("production", m(
    "How do I implement a pausable program in Anchor?",
    """```rust
#[account]
#[derive(InitSpace)]
pub struct Config {
    pub admin: Pubkey,
    pub paused: bool,
    pub bump: u8,
}

pub fn pause(ctx: Context<AdminOnly>) -> Result<()> {
    ctx.accounts.config.paused = true;
    Ok(())
}

pub fn unpause(ctx: Context<AdminOnly>) -> Result<()> {
    ctx.accounts.config.paused = false;
    Ok(())
}

pub fn user_action(ctx: Context<UserAction>) -> Result<()> {
    require!(!ctx.accounts.config.paused, MyError::Paused);
    // ... normal logic
    Ok(())
}

#[derive(Accounts)]
pub struct AdminOnly<'info> {
    #[account(mut, seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, Config>,
    pub admin: Signer<'info>,
}

#[derive(Accounts)]
pub struct UserAction<'info> {
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, Config>,
    // ... other accounts
}
```
Use a global config PDA with a `paused` flag. Check it in every user-facing instruction.""")))

GLAN.append(("production", m(
    "How do I implement admin rotation (transfer ownership) safely?",
    """Use a two-step process to prevent accidental lockout:

```rust
#[account]
#[derive(InitSpace)]
pub struct Config {
    pub admin: Pubkey,
    pub pending_admin: Option<Pubkey>,
    pub bump: u8,
}

pub fn propose_admin(ctx: Context<AdminOnly>, new_admin: Pubkey) -> Result<()> {
    ctx.accounts.config.pending_admin = Some(new_admin);
    Ok(())
}

pub fn accept_admin(ctx: Context<AcceptAdmin>) -> Result<()> {
    let config = &mut ctx.accounts.config;
    require!(
        config.pending_admin == Some(ctx.accounts.new_admin.key()),
        MyError::NotPendingAdmin
    );
    config.admin = ctx.accounts.new_admin.key();
    config.pending_admin = None;
    Ok(())
}

#[derive(Accounts)]
pub struct AcceptAdmin<'info> {
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, Config>,
    pub new_admin: Signer<'info>,  // new admin must sign to accept
}
```
Two-step prevents transferring to a wrong address — the new admin must actively accept.""")))

GLAN.append(("production", m(
    "How do I implement versioned account migration in Anchor?",
    """```rust
#[account]
#[derive(InitSpace)]
pub struct AccountV2 {
    pub version: u8,         // 1 = v1, 2 = v2
    pub authority: Pubkey,
    pub value: u64,
    pub new_field: u64,      // added in v2
    pub bump: u8,
}

pub fn migrate_v1_to_v2(ctx: Context<Migrate>) -> Result<()> {
    let account = &mut ctx.accounts.account;
    require!(account.version == 1, MyError::AlreadyMigrated);

    account.new_field = 0;  // default value for new field
    account.version = 2;
    Ok(())
}

#[derive(Accounts)]
pub struct Migrate<'info> {
    #[account(
        mut,
        realloc = 8 + AccountV2::INIT_SPACE,
        realloc::payer = payer,
        realloc::zero = false,
        has_one = authority,
    )]
    pub account: Account<'info, AccountV2>,
    pub authority: Signer<'info>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```
Use `realloc` to grow the account, a version field to track schema version, and a migration instruction users call once.""")))

# ── Multisig & Governance ─────────────────────────────────────────────────

GLAN.append(("governance", m(
    "How do I implement a basic 2-of-3 multisig in Anchor?",
    """```rust
#[account]
#[derive(InitSpace)]
pub struct Multisig {
    pub signers: [Pubkey; 3],
    pub threshold: u8,  // 2
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Transaction {
    pub multisig: Pubkey,
    pub instruction_data: Vec<u8>,
    pub approvals: [bool; 3],
    pub executed: bool,
    pub bump: u8,
}

pub fn approve(ctx: Context<Approve>) -> Result<()> {
    let ms = &ctx.accounts.multisig;
    let tx = &mut ctx.accounts.transaction;
    let signer = ctx.accounts.signer.key();

    // Find signer index
    let idx = ms.signers.iter().position(|s| *s == signer)
        .ok_or(MsError::NotASigner)?;

    require!(!tx.approvals[idx], MsError::AlreadyApproved);
    tx.approvals[idx] = true;

    // Check if threshold met
    let approval_count = tx.approvals.iter().filter(|a| **a).count() as u8;
    if approval_count >= ms.threshold {
        // Execute the transaction via CPI
        // ...
        tx.executed = true;
    }
    Ok(())
}

#[error_code]
pub enum MsError {
    #[msg("Not a signer")] NotASigner,
    #[msg("Already approved")] AlreadyApproved,
}
```
Each signer calls `approve`. When threshold (2) is reached, the transaction auto-executes.""")))

# ── Client Patterns ───────────────────────────────────────────────────────

GLAN.append(("typescript", m(
    "How do I use getProgramAccounts with filters efficiently?",
    """```typescript
import { Connection, PublicKey } from "@solana/web3.js";

const connection = new Connection("https://api.mainnet-beta.solana.com");

// Fetch all accounts of a specific type, filtered by a field
const accounts = await connection.getProgramAccounts(programId, {
  filters: [
    { dataSize: 165 },  // exact account size (filters by type)
    {
      memcmp: {
        offset: 8,      // skip 8-byte discriminator
        bytes: userPubkey.toBase58(),  // match authority field (32 bytes)
      },
    },
  ],
  // Only fetch the fields you need (saves bandwidth)
  dataSlice: {
    offset: 40,   // start after discriminator + authority
    length: 8,    // just read the u64 balance field
  },
});

// Parse results
for (const { pubkey, account } of accounts) {
  const balance = new DataView(account.data.buffer).getBigUint64(0, true); // little-endian
  console.log(pubkey.toBase58(), "balance:", balance.toString());
}
```
`dataSlice` reduces data transfer — critical when fetching thousands of accounts. `memcmp` filters run on the RPC node, not client-side.""")))

GLAN.append(("typescript", m(
    "How do I integrate Jupiter swap in TypeScript?",
    """```typescript
import { Connection, PublicKey, VersionedTransaction } from "@solana/web3.js";

async function jupiterSwap(
  connection: Connection,
  userPubkey: PublicKey,
  inputMint: string,  // e.g., SOL mint
  outputMint: string, // e.g., USDC mint
  amount: number,     // in smallest unit (lamports)
  slippageBps: number = 50, // 0.5%
) {
  // 1. Get quote
  const quoteUrl = `https://quote-api.jup.ag/v6/quote?inputMint=${inputMint}&outputMint=${outputMint}&amount=${amount}&slippageBps=${slippageBps}`;
  const quoteResp = await fetch(quoteUrl);
  const quote = await quoteResp.json();

  // 2. Get swap transaction
  const swapResp = await fetch("https://quote-api.jup.ag/v6/swap", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quoteResponse: quote,
      userPublicKey: userPubkey.toBase58(),
      wrapAndUnwrapSol: true,
      dynamicComputeUnitLimit: true,
      prioritizationFeeLamports: "auto",
    }),
  });
  const { swapTransaction } = await swapResp.json();

  // 3. Deserialize and sign
  const tx = VersionedTransaction.deserialize(Buffer.from(swapTransaction, "base64"));
  // tx.sign([wallet]); // sign with user's keypair
  return tx;
}
```
Jupiter aggregates all Solana DEXes. Always set `slippageBps` and use `dynamicComputeUnitLimit` for optimal fees.""")))

GLAN.append(("typescript", m(
    "How do I subscribe to account changes in real-time?",
    """```typescript
import { Connection, PublicKey } from "@solana/web3.js";
import * as anchor from "@coral-xyz/anchor";

const connection = new Connection("wss://api.mainnet-beta.solana.com", "confirmed");

// 1. Subscribe to a specific account
const subId = connection.onAccountChange(
  accountPubkey,
  (accountInfo, context) => {
    console.log("Slot:", context.slot);
    console.log("Data:", accountInfo.data);
    // Decode with Anchor:
    const decoded = program.coder.accounts.decode("MyAccount", accountInfo.data);
    console.log("Balance:", decoded.balance.toString());
  },
  "confirmed",
);

// 2. Subscribe to all accounts of a program
const progSubId = connection.onProgramAccountChange(
  programId,
  (keyedAccountInfo, context) => {
    console.log("Account:", keyedAccountInfo.accountId.toBase58());
    // Process change...
  },
  "confirmed",
  [{ dataSize: 165 }], // optional filters
);

// 3. Subscribe to logs
const logSubId = connection.onLogs(
  programId,
  (logs) => {
    console.log("TX:", logs.signature);
    console.log("Logs:", logs.logs);
  },
  "confirmed",
);

// Cleanup
connection.removeAccountChangeListener(subId);
```
Use `wss://` WebSocket URL for subscriptions. Always clean up listeners to prevent memory leaks.""")))

GLAN.append(("typescript", m(
    "How do I handle transaction confirmation properly?",
    """```typescript
import { Connection, Transaction, sendAndConfirmTransaction } from "@solana/web3.js";

// Method 1: Simple (blocks until confirmed)
const sig = await sendAndConfirmTransaction(connection, tx, [payer], {
  commitment: "confirmed",
  maxRetries: 3,
});

// Method 2: Non-blocking with polling
const sig = await connection.sendTransaction(tx, [payer]);
const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash();

const confirmation = await connection.confirmTransaction({
  signature: sig,
  blockhash,
  lastValidBlockHeight,
}, "confirmed");

if (confirmation.value.err) {
  throw new Error(`TX failed: ${JSON.stringify(confirmation.value.err)}`);
}

// Method 3: Retry pattern for congestion
async function sendWithRetry(connection, tx, signers, maxRetries = 5) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash();
      tx.recentBlockhash = blockhash;
      tx.lastValidBlockHeight = lastValidBlockHeight;
      return await sendAndConfirmTransaction(connection, tx, signers, {
        commitment: "confirmed",
      });
    } catch (e) {
      if (i === maxRetries - 1) throw e;
      await new Promise(r => setTimeout(r, 1000 * (i + 1))); // backoff
    }
  }
}
```
Always use `lastValidBlockHeight` for expiry-based confirmation instead of timeout-based.""")))

# ── Testing Patterns ──────────────────────────────────────────────────────

GLAN.append(("testing", m(
    "How do I test error cases in Anchor with Bankrun?",
    """```typescript
import { startAnchor } from "solana-bankrun";
import { BankrunProvider } from "anchor-bankrun";
import assert from "node:assert";

describe("error handling", () => {
  it("rejects unauthorized access", async () => {
    const context = await startAnchor(".", [], []);
    const provider = new BankrunProvider(context);
    const program = new Program(idl, provider);

    const attacker = anchor.web3.Keypair.generate();

    try {
      await program.methods
        .adminOnlyFunction()
        .accounts({ config: configPda, admin: attacker.publicKey })
        .signers([attacker])
        .rpc();
      assert.fail("Should have thrown");
    } catch (err) {
      // Check for specific Anchor error
      assert.ok(err.error.errorCode.number === 2001); // ConstraintHasOne
      // Or check message:
      assert.ok(err.error.errorMessage.includes("has one"));
    }
  });

  it("rejects zero amount deposit", async () => {
    try {
      await program.methods.deposit(new anchor.BN(0)).accounts({/*...*/}).rpc();
      assert.fail("Should have thrown");
    } catch (err) {
      assert.equal(err.error.errorCode.code, "ZeroAmount");
      assert.equal(err.error.errorCode.number, 6000);
    }
  });
});
```
Test both success AND failure paths. Check specific error codes, not just that it threw.""")))

GLAN.append(("testing", m(
    "How do I manipulate time in Anchor tests?",
    """```typescript
import { startAnchor, Clock } from "solana-bankrun";

it("enforces timelock", async () => {
  const context = await startAnchor(".", [], []);

  // Lock tokens with 1-day timelock
  await program.methods.lock(new anchor.BN(86400)).accounts({/*...*/}).rpc();

  // Try to unlock immediately — should fail
  try {
    await program.methods.unlock().accounts({/*...*/}).rpc();
    assert.fail("Should be locked");
  } catch (err) {
    assert.equal(err.error.errorCode.code, "TooEarly");
  }

  // Fast-forward time by 1 day
  const currentClock = await context.banksClient.getClock();
  const newClock = new Clock(
    currentClock.slot,
    currentClock.epochStartTimestamp,
    currentClock.epoch,
    currentClock.leaderScheduleEpoch,
    BigInt(currentClock.unixTimestamp) + BigInt(86400), // +1 day
  );
  context.setClock(newClock);

  // Now unlock should succeed
  await program.methods.unlock().accounts({/*...*/}).rpc();
});
```
Bankrun's `setClock` lets you manipulate `Clock::get()` for time-dependent tests without waiting.""")))

GLAN.append(("testing", m(
    "How do I test token operations in Anchor with Bankrun?",
    """```typescript
import { startAnchor } from "solana-bankrun";
import { createMint, createAccount, mintTo } from "spl-token-bankrun";

it("deposits tokens correctly", async () => {
  const context = await startAnchor(".", [], []);
  const provider = new BankrunProvider(context);
  const payer = provider.wallet.payer;

  // Create mint and token accounts
  const mint = await createMint(context.banksClient, payer, payer.publicKey, null, 6);
  const userToken = await createAccount(context.banksClient, payer, mint, payer.publicKey);
  const vaultToken = await createAccount(context.banksClient, payer, mint, vaultPda);

  // Mint tokens to user
  await mintTo(context.banksClient, payer, mint, userToken, payer, 1_000_000);

  // Test deposit
  await program.methods
    .deposit(new anchor.BN(500_000))
    .accounts({
      userToken, vaultToken, mint,
      user: payer.publicKey,
      tokenProgram: TOKEN_PROGRAM_ID,
      systemProgram: SystemProgram.programId,
    })
    .rpc();

  // Verify balances
  const userAcc = await getAccount(context.banksClient, userToken);
  const vaultAcc = await getAccount(context.banksClient, vaultToken);
  assert.equal(userAcc.amount, BigInt(500_000));
  assert.equal(vaultAcc.amount, BigInt(500_000));
});
```
`spl-token-bankrun` provides helpers that work with Bankrun's simulated environment.""")))

# ── Solana Concepts ───────────────────────────────────────────────────────

GLAN.append(("concepts", m(
    "Explain the anatomy of a Solana transaction.",
    """A Solana transaction has:

```
Transaction {
  signatures: [Signature],           // Ed25519 sigs from required signers
  message: {
    header: {
      num_required_signatures: u8,   // how many sigs needed
      num_readonly_signed: u8,       // signed but read-only
      num_readonly_unsigned: u8,     // unsigned and read-only
    },
    account_keys: [Pubkey],          // all accounts referenced
    recent_blockhash: Hash,          // expires after ~60 seconds
    instructions: [{
      program_id_index: u8,          // index into account_keys
      accounts: [u8],                // indices into account_keys
      data: [u8],                    // instruction data (borsh-encoded)
    }],
  }
}
```

**Limits:**
- Max size: **1232 bytes** (MTU - headers)
- Max accounts: ~35 (without lookup tables), ~256 (with ALTs)
- Max instructions: limited by size
- Max compute: 1,400,000 CU per transaction
- Blockhash validity: ~60 seconds (~150 slots)

**Key insight:** All accounts are declared upfront in `account_keys`. This lets the runtime schedule non-conflicting transactions in parallel — the core of Solana's throughput.""")))

GLAN.append(("concepts", m(
    "How does rent work on Solana?",
    """Every account must hold enough SOL to be **rent-exempt** (pay 2 years of rent upfront). If not, the account is garbage-collected.

**Rent-exempt minimum:**
```
rent = account_size_in_bytes * 6.96e-6 SOL/byte/epoch * 2 years
     ≈ account_size * 0.00000696 * 2 * 365.25/2 (epochs/year)
```

Common sizes:
| Account | Size | Rent-exempt |
|---|---|---|
| System account (0 data) | 0 | 0.00089 SOL |
| Token account | 165 bytes | 0.00204 SOL |
| Mint | 82 bytes | 0.00146 SOL |
| 1KB data | 1024 bytes | 0.00796 SOL |

In Anchor, `init` automatically calculates and charges rent-exempt minimum. The payer provides the SOL.

When you close an account (`close = recipient`), all lamports (including rent) transfer to the recipient.

```rust
// Check rent programmatically
let rent = Rent::get()?;
let min_balance = rent.minimum_balance(account_data_len);
```

Since 2022, all new accounts MUST be rent-exempt. The old "pay rent per epoch" model is deprecated.""")))

GLAN.append(("concepts", m(
    "What are address lookup tables and when should I use them?",
    """Address Lookup Tables (ALTs) compress transaction size by replacing 32-byte pubkeys with 1-byte indices.

**Without ALT:** Each account = 32 bytes. 35 accounts = 1120 bytes (nearly fills the 1232-byte limit).

**With ALT:** Each account = 1 byte index. 256 accounts fit easily.

**When to use:**
- Transactions referencing many accounts (DeFi swaps, batch operations)
- Jupiter swaps (often need 20+ accounts)
- Any transaction hitting the 1232-byte size limit

**Create an ALT:**
```typescript
const [createIx, lookupTableAddress] = AddressLookupTableProgram.createLookupTable({
  authority: payer.publicKey,
  payer: payer.publicKey,
  recentSlot: await connection.getSlot(),
});

// Add addresses (can add up to 256)
const extendIx = AddressLookupTableProgram.extendLookupTable({
  lookupTable: lookupTableAddress,
  authority: payer.publicKey,
  payer: payer.publicKey,
  addresses: [programId, tokenProgramId, /*...all your accounts...*/],
});

// IMPORTANT: Wait 1 slot after creation before using
// ALTs take 1 slot to activate
```

Then use with versioned transactions (`TransactionMessage.compileToV0Message([lookupTable])`).""")))

# ── Runtime & Sysvars ─────────────────────────────────────────────────────

GLAN.append(("runtime", m(
    "How do I access sysvars in Anchor?",
    """Common sysvars and how to access them:

```rust
use anchor_lang::prelude::*;

pub fn my_instruction(ctx: Context<MyCtx>) -> Result<()> {
    // Clock: slot, timestamp, epoch
    let clock = Clock::get()?;
    msg!("Timestamp: {}", clock.unix_timestamp);
    msg!("Slot: {}", clock.slot);
    msg!("Epoch: {}", clock.epoch);

    // Rent: minimum balance calculation
    let rent = Rent::get()?;
    let min_balance = rent.minimum_balance(200); // for 200-byte account
    msg!("Min rent: {} lamports", min_balance);

    // EpochSchedule: epoch timing info
    let schedule = EpochSchedule::get()?;
    let epoch_for_slot = schedule.get_epoch(clock.slot);

    // Recent blockhashes (via account)
    // let recent = &ctx.accounts.recent_blockhashes;

    // Instruction sysvar (for introspection)
    // let ix_sysvar = &ctx.accounts.instruction_sysvar;
    Ok(())
}

// For sysvars that need account access:
#[derive(Accounts)]
pub struct MyCtx<'info> {
    /// CHECK: Instructions sysvar
    #[account(address = anchor_lang::solana_program::sysvar::instructions::ID)]
    pub instruction_sysvar: AccountInfo<'info>,
}
```

`Clock::get()`, `Rent::get()`, and `EpochSchedule::get()` don't need account references — they use the sysvar cache (cheaper). The Instructions sysvar still requires an account.""")))

GLAN.append(("runtime", m(
    "How do I use instruction introspection to verify CPI callers?",
    """```rust
use anchor_lang::prelude::*;
use anchor_lang::solana_program::sysvar::instructions::{
    self, get_instruction_relative,
};

pub fn protected_action(ctx: Context<Protected>) -> Result<()> {
    // Get the current instruction index
    let ix_sysvar = &ctx.accounts.instruction_sysvar;
    let current_ix = instructions::load_current_index_checked(ix_sysvar)?;

    // Verify no CPI called us (prevent sandwich attacks)
    // If called via CPI, the caller's program ID appears in the stack
    let ix = get_instruction_relative(0, ix_sysvar)?;
    require!(
        ix.program_id == crate::ID,
        MyError::UnauthorizedCpi
    );

    // Or: verify a specific instruction was called before this one
    if current_ix > 0 {
        let prev_ix = get_instruction_relative(-1, ix_sysvar)?;
        // Check prev_ix.program_id, prev_ix.data, etc.
    }

    Ok(())
}

#[derive(Accounts)]
pub struct Protected<'info> {
    /// CHECK: Instructions sysvar
    #[account(address = instructions::ID)]
    pub instruction_sysvar: AccountInfo<'info>,
}
```
Instruction introspection is useful for: CPI guard (prevent being called via CPI), requiring a specific instruction before yours (e.g., Ed25519 signature verification), and flash loan callbacks.""")))

# ── Integration Patterns ──────────────────────────────────────────────────

GLAN.append(("integration", m(
    "How do I use Helius enhanced transactions API?",
    """```typescript
const HELIUS_KEY = "your-api-key";

// 1. Get parsed transaction history for an address
const response = await fetch(
  `https://api.helius.xyz/v0/addresses/${address}/transactions?api-key=${HELIUS_KEY}&type=SWAP`
);
const transactions = await response.json();

// Each transaction is enriched:
for (const tx of transactions) {
  console.log("Type:", tx.type);           // "SWAP", "TRANSFER", "NFT_SALE", etc.
  console.log("Source:", tx.source);        // "JUPITER", "RAYDIUM", etc.
  console.log("Fee:", tx.fee);
  console.log("Timestamp:", tx.timestamp);

  // Token transfers are parsed
  for (const transfer of tx.tokenTransfers) {
    console.log(`${transfer.fromUserAccount} → ${transfer.toUserAccount}`);
    console.log(`Amount: ${transfer.tokenAmount} ${transfer.mint}`);
  }
}

// 2. Parse a single transaction
const parsed = await fetch(
  `https://api.helius.xyz/v0/transactions/?api-key=${HELIUS_KEY}`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transactions: [txSignature] }),
  }
);
```
Helius parses raw Solana transactions into human-readable types, sources, and token transfers. Free tier: 1M credits/month.""")))

GLAN.append(("integration", m(
    "How do I use Switchboard VRF for on-chain randomness?",
    """```rust
use anchor_lang::prelude::*;
use switchboard_solana::prelude::*;

#[program]
pub mod lottery {
    use super::*;

    pub fn request_randomness(ctx: Context<RequestRandom>) -> Result<()> {
        // Request VRF from Switchboard
        let vrf_request_randomness = VrfRequestRandomness {
            authority: ctx.accounts.state.to_account_info(),
            vrf: ctx.accounts.vrf.to_account_info(),
            oracle_queue: ctx.accounts.oracle_queue.to_account_info(),
            queue_authority: ctx.accounts.queue_authority.to_account_info(),
            data_buffer: ctx.accounts.data_buffer.to_account_info(),
            permission: ctx.accounts.permission.to_account_info(),
            escrow: ctx.accounts.escrow.to_account_info(),
            payer_wallet: ctx.accounts.payer_wallet.to_account_info(),
            payer_authority: ctx.accounts.payer.to_account_info(),
            recent_blockhashes: ctx.accounts.recent_blockhashes.to_account_info(),
            program_state: ctx.accounts.program_state.to_account_info(),
            token_program: ctx.accounts.token_program.to_account_info(),
        };

        // PDA signs the request
        let seeds = &[b"state".as_ref(), &[ctx.bumps.state]];
        vrf_request_randomness.invoke_signed(ctx.accounts.switchboard.to_account_info(), &[seeds])?;

        Ok(())
    }

    // Callback: Switchboard calls this with the random result
    pub fn consume_randomness(ctx: Context<ConsumeRandom>) -> Result<()> {
        let vrf = ctx.accounts.vrf.load()?;
        let result_buffer = vrf.get_result()?;

        // Convert to a usable random number
        let random_value = u64::from_le_bytes(result_buffer[0..8].try_into().unwrap());
        let winner_index = random_value % ctx.accounts.state.num_participants;

        ctx.accounts.state.winner = winner_index;
        Ok(())
    }
}
```
Switchboard VRF provides verifiable randomness — the oracle proves the result is unbiased. Essential for lotteries, games, and fair NFT mints.""")))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    glan_records = [rec(content, "glan", cat) for cat, content in GLAN]
    ct = write_jsonl(glan_records, OUT_DIR / "synthetic-glan-extra.jsonl")
    print(f"✓ {ct} GLAN records → synthetic-glan-extra.jsonl")
    print(f"\nTotal: {ct}")

if __name__ == "__main__":
    main()
