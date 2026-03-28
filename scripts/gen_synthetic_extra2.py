#!/usr/bin/env python3
"""Additional synthetic data — Evol-Instruct chains + DPO preference pairs + OSS-Instruct."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from schema import Record, write_jsonl

SYSTEM = "You are an expert Solana and Anchor developer. Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns."
OUT_DIR = Path(__file__).parent.parent / "data" / "processed"

def m(u, a):
    return json.dumps([{"role":"system","content":SYSTEM},{"role":"user","content":u},{"role":"assistant","content":a}], ensure_ascii=False)

EVOL = []
DPO = []  # (chosen, rejected, category)
OSS = []

# ═══════════════════════════════════════════════════════════════════════════════
# EVOL-INSTRUCT: AMM chain L0→L2
# ═══════════════════════════════════════════════════════════════════════════════

EVOL.append(("amm", "L0", m(
    "Write a basic constant-product AMM swap function in Anchor.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod amm {
    use super::*;

    pub fn swap(ctx: Context<Swap>, amount_in: u64, min_out: u64) -> Result<()> {
        let r_a = ctx.accounts.pool_a.amount as u128;
        let r_b = ctx.accounts.pool_b.amount as u128;
        let a_in = amount_in as u128;

        // x * y = k → out = r_b * a_in / (r_a + a_in)
        let out = r_b.checked_mul(a_in).unwrap() / r_a.checked_add(a_in).unwrap();
        let amount_out = out as u64;
        require!(amount_out >= min_out, AmmError::Slippage);

        // User sends token A to pool
        token::transfer(CpiContext::new(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.user_a.to_account_info(),
                to: ctx.accounts.pool_a.to_account_info(),
                authority: ctx.accounts.user.to_account_info() }), amount_in)?;

        // Pool sends token B to user (PDA signer)
        let seeds = &[b"pool".as_ref(), &[ctx.bumps.pool_auth]];
        token::transfer(CpiContext::new_with_signer(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.pool_b.to_account_info(),
                to: ctx.accounts.user_b.to_account_info(),
                authority: ctx.accounts.pool_auth.to_account_info() }, &[seeds]), amount_out)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Swap<'info> {
    #[account(mut)] pub pool_a: Account<'info, TokenAccount>,
    #[account(mut)] pub pool_b: Account<'info, TokenAccount>,
    #[account(mut)] pub user_a: Account<'info, TokenAccount>,
    #[account(mut)] pub user_b: Account<'info, TokenAccount>,
    /// CHECK: PDA pool authority
    #[account(seeds = [b"pool"], bump)]
    pub pool_auth: UncheckedAccount<'info>,
    pub user: Signer<'info>,
    pub token_program: Program<'info, Token>,
}

#[error_code]
pub enum AmmError { #[msg("Slippage exceeded")] Slippage }
```""")))

EVOL.append(("amm", "L1", m(
    "Extend the AMM with add_liquidity and remove_liquidity using LP tokens.",
    """```rust
pub fn add_liquidity(ctx: Context<AddLiquidity>, max_a: u64, max_b: u64) -> Result<()> {
    let pool = &mut ctx.accounts.pool_state;
    let lp_mint_supply = ctx.accounts.lp_mint.supply;

    let (deposit_a, deposit_b, lp_to_mint) = if lp_mint_supply == 0 {
        // First deposit: mint sqrt(a*b) LP tokens
        let lp = ((max_a as f64) * (max_b as f64)).sqrt() as u64;
        (max_a, max_b, lp)
    } else {
        // Proportional deposit
        let r_a = ctx.accounts.pool_a.amount;
        let r_b = ctx.accounts.pool_b.amount;
        let lp_a = (max_a as u128) * (lp_mint_supply as u128) / (r_a as u128);
        let lp_b = (max_b as u128) * (lp_mint_supply as u128) / (r_b as u128);
        let lp = lp_a.min(lp_b) as u64;
        let dep_a = (lp as u128 * r_a as u128 / lp_mint_supply as u128) as u64;
        let dep_b = (lp as u128 * r_b as u128 / lp_mint_supply as u128) as u64;
        (dep_a, dep_b, lp)
    };

    require!(lp_to_mint > 0, AmmError::ZeroLp);

    // Transfer tokens A and B from user to pool
    token::transfer(CpiContext::new(/*...*/), deposit_a)?;
    token::transfer(CpiContext::new(/*...*/), deposit_b)?;

    // Mint LP tokens to user (PDA signer on mint authority)
    let seeds = &[b"pool".as_ref(), &[ctx.bumps.pool_auth]];
    token::mint_to(CpiContext::new_with_signer(/*...LP mint...*/,&[seeds]), lp_to_mint)?;
    Ok(())
}

pub fn remove_liquidity(ctx: Context<RemoveLiquidity>, lp_amount: u64) -> Result<()> {
    let supply = ctx.accounts.lp_mint.supply as u128;
    let share = lp_amount as u128;

    let out_a = (share * ctx.accounts.pool_a.amount as u128 / supply) as u64;
    let out_b = (share * ctx.accounts.pool_b.amount as u128 / supply) as u64;

    // Burn LP tokens
    token::burn(CpiContext::new(/*...*/), lp_amount)?;

    // Transfer pool tokens to user (PDA signer)
    let seeds = &[b"pool".as_ref(), &[ctx.bumps.pool_auth]];
    token::transfer(CpiContext::new_with_signer(/*...A...*/,&[seeds]), out_a)?;
    token::transfer(CpiContext::new_with_signer(/*...B...*/,&[seeds]), out_b)?;
    Ok(())
}

#[error_code]
pub enum AmmError {
    #[msg("Slippage")] Slippage,
    #[msg("Zero LP")] ZeroLp,
}
```
LP tokens represent proportional ownership. First depositor sets the price ratio.""")))

EVOL.append(("amm", "L2", m(
    "Add swap fees (0.3%), protocol fee split, and slippage protection to the AMM.",
    """```rust
const SWAP_FEE_BPS: u128 = 30;     // 0.3%
const PROTOCOL_FEE_BPS: u128 = 5;  // 0.05% goes to protocol

pub fn swap_with_fees(ctx: Context<Swap>, amount_in: u64, min_out: u64) -> Result<()> {
    let r_a = ctx.accounts.pool_a.amount as u128;
    let r_b = ctx.accounts.pool_b.amount as u128;
    let a_in = amount_in as u128;

    // Deduct fee before calculating output
    let fee = a_in * SWAP_FEE_BPS / 10_000;
    let protocol_fee = a_in * PROTOCOL_FEE_BPS / 10_000;
    let net_in = a_in - fee;

    // Constant product: out = r_b * net_in / (r_a + net_in)
    let amount_out = (r_b * net_in / (r_a + net_in)) as u64;

    // Slippage check
    require!(amount_out >= min_out, AmmError::Slippage);

    // Check price impact isn't too high (max 10%)
    let price_impact = fee * 10_000 / a_in;
    require!(price_impact <= 1000, AmmError::PriceImpact);

    // Transfer amount_in from user to pool (fee stays in pool, growing LP value)
    token::transfer(CpiContext::new(/*...*/), amount_in)?;

    // Transfer protocol fee to treasury
    if protocol_fee > 0 {
        let seeds = &[b"pool".as_ref(), &[ctx.bumps.pool_auth]];
        token::transfer(CpiContext::new_with_signer(/*...to treasury...*/,&[seeds]),
            protocol_fee as u64)?;
    }

    // Transfer output to user
    let seeds = &[b"pool".as_ref(), &[ctx.bumps.pool_auth]];
    token::transfer(CpiContext::new_with_signer(/*...*/,&[seeds]), amount_out)?;

    emit!(SwapEvent { user: ctx.accounts.user.key(), amount_in, amount_out, fee: fee as u64 });
    Ok(())
}

#[event]
pub struct SwapEvent { pub user: Pubkey, pub amount_in: u64, pub amount_out: u64, pub fee: u64 }

#[error_code]
pub enum AmmError {
    #[msg("Slippage exceeded")] Slippage,
    #[msg("Price impact too high")] PriceImpact,
    #[msg("Zero LP")] ZeroLp,
}
```
Fees stay in the pool (growing LP token value). Protocol fee goes to treasury. Always check slippage and price impact.""")))

# ═══════════════════════════════════════════════════════════════════════════════
# EVOL-INSTRUCT: NFT Marketplace chain L0→L2
# ═══════════════════════════════════════════════════════════════════════════════

EVOL.append(("nft-market", "L0", m(
    "Write a basic NFT listing program where sellers can list NFTs for a fixed price.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod marketplace {
    use super::*;

    pub fn list(ctx: Context<ListNft>, price: u64) -> Result<()> {
        require!(price > 0, MktError::ZeroPrice);

        // Transfer NFT from seller to escrow
        token::transfer(CpiContext::new(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.seller_nft.to_account_info(),
                to: ctx.accounts.escrow_nft.to_account_info(),
                authority: ctx.accounts.seller.to_account_info() }), 1)?;

        let listing = &mut ctx.accounts.listing;
        listing.seller = ctx.accounts.seller.key();
        listing.mint = ctx.accounts.nft_mint.key();
        listing.price = price;
        listing.bump = ctx.bumps.listing;
        Ok(())
    }

    pub fn buy(ctx: Context<BuyNft>) -> Result<()> {
        let listing = &ctx.accounts.listing;

        // Pay seller in SOL
        anchor_lang::system_program::transfer(
            CpiContext::new(ctx.accounts.system_program.to_account_info(),
                anchor_lang::system_program::Transfer {
                    from: ctx.accounts.buyer.to_account_info(),
                    to: ctx.accounts.seller.to_account_info() }),
            listing.price)?;

        // Transfer NFT from escrow to buyer (PDA signer)
        let mint = ctx.accounts.nft_mint.key();
        let seeds = &[b"escrow", mint.as_ref(), &[ctx.bumps.escrow_nft]];
        token::transfer(CpiContext::new_with_signer(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.escrow_nft.to_account_info(),
                to: ctx.accounts.buyer_nft.to_account_info(),
                authority: ctx.accounts.escrow_nft.to_account_info() }, &[seeds]), 1)?;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Listing {
    pub seller: Pubkey, pub mint: Pubkey, pub price: u64, pub bump: u8,
}

#[error_code]
pub enum MktError { #[msg("Price must be > 0")] ZeroPrice }
```""")))

EVOL.append(("nft-market", "L1", m(
    "Add cancel listing and marketplace fees to the NFT marketplace.",
    """```rust
const MARKETPLACE_FEE_BPS: u64 = 250; // 2.5%

pub fn buy(ctx: Context<BuyNft>) -> Result<()> {
    let listing = &ctx.accounts.listing;
    let price = listing.price;

    // Calculate marketplace fee
    let fee = price.checked_mul(MARKETPLACE_FEE_BPS).unwrap() / 10_000;
    let seller_amount = price - fee;

    // Pay seller (minus fee)
    system_program::transfer(CpiContext::new(/*...*/), seller_amount)?;

    // Pay marketplace fee to treasury
    if fee > 0 {
        system_program::transfer(CpiContext::new(/*...to treasury...*/), fee)?;
    }

    // Transfer NFT to buyer (PDA signer)
    let mint = ctx.accounts.nft_mint.key();
    let seeds = &[b"escrow", mint.as_ref(), &[ctx.bumps.escrow_nft]];
    token::transfer(CpiContext::new_with_signer(/*...*/,&[seeds]), 1)?;

    emit!(SaleEvent { mint: listing.mint, seller: listing.seller,
        buyer: ctx.accounts.buyer.key(), price, fee });
    Ok(())
}

pub fn cancel(ctx: Context<CancelListing>) -> Result<()> {
    // Return NFT from escrow to seller (PDA signer)
    let mint = ctx.accounts.nft_mint.key();
    let seeds = &[b"escrow", mint.as_ref(), &[ctx.bumps.escrow_nft]];
    token::transfer(CpiContext::new_with_signer(/*...*/,&[seeds]), 1)?;
    // Listing account closed via `close = seller` constraint
    Ok(())
}

#[derive(Accounts)]
pub struct CancelListing<'info> {
    #[account(mut, close = seller, has_one = seller,
        seeds = [b"listing", nft_mint.key().as_ref()], bump = listing.bump)]
    pub listing: Account<'info, Listing>,
    #[account(mut)] pub seller: Signer<'info>,
    // ... escrow accounts
}

#[event]
pub struct SaleEvent { pub mint: Pubkey, pub seller: Pubkey, pub buyer: Pubkey, pub price: u64, pub fee: u64 }
```
Seller can cancel to get NFT back. Marketplace takes 2.5% fee on sales.""")))

EVOL.append(("nft-market", "L2", m(
    "Add English auction functionality to the NFT marketplace.",
    """```rust
#[account]
#[derive(InitSpace)]
pub struct Auction {
    pub seller: Pubkey,
    pub mint: Pubkey,
    pub highest_bidder: Pubkey,
    pub highest_bid: u64,
    pub min_bid: u64,
    pub end_time: i64,
    pub settled: bool,
    pub bump: u8,
}

pub fn create_auction(ctx: Context<CreateAuction>, min_bid: u64, duration: i64) -> Result<()> {
    let clock = Clock::get()?;

    // Transfer NFT to escrow
    token::transfer(CpiContext::new(/*...*/), 1)?;

    let auction = &mut ctx.accounts.auction;
    auction.seller = ctx.accounts.seller.key();
    auction.mint = ctx.accounts.nft_mint.key();
    auction.min_bid = min_bid;
    auction.highest_bid = 0;
    auction.highest_bidder = Pubkey::default();
    auction.end_time = clock.unix_timestamp + duration;
    auction.settled = false;
    auction.bump = ctx.bumps.auction;
    Ok(())
}

pub fn place_bid(ctx: Context<PlaceBid>, bid_amount: u64) -> Result<()> {
    let clock = Clock::get()?;
    let auction = &mut ctx.accounts.auction;

    require!(clock.unix_timestamp < auction.end_time, AucError::Ended);
    require!(bid_amount >= auction.min_bid, AucError::BidTooLow);
    require!(bid_amount > auction.highest_bid, AucError::BidTooLow);

    // Refund previous highest bidder
    if auction.highest_bid > 0 {
        // Transfer SOL back to previous bidder from escrow
        **ctx.accounts.bid_escrow.to_account_info().try_borrow_mut_lamports()? -= auction.highest_bid;
        **ctx.accounts.prev_bidder.to_account_info().try_borrow_mut_lamports()? += auction.highest_bid;
    }

    // Accept new bid: transfer SOL to escrow
    system_program::transfer(CpiContext::new(/*...*/), bid_amount)?;

    auction.highest_bidder = ctx.accounts.bidder.key();
    auction.highest_bid = bid_amount;

    // Extend auction if bid in last 5 minutes (anti-sniping)
    if auction.end_time - clock.unix_timestamp < 300 {
        auction.end_time = clock.unix_timestamp + 300;
    }
    Ok(())
}

pub fn settle_auction(ctx: Context<SettleAuction>) -> Result<()> {
    let clock = Clock::get()?;
    let auction = &mut ctx.accounts.auction;

    require!(clock.unix_timestamp >= auction.end_time, AucError::NotEnded);
    require!(!auction.settled, AucError::AlreadySettled);

    if auction.highest_bid > 0 {
        // Transfer NFT to winner, SOL to seller (minus fee)
        let fee = auction.highest_bid * 250 / 10_000;
        // ... transfers with PDA signing ...
    } else {
        // No bids: return NFT to seller
    }

    auction.settled = true;
    Ok(())
}

#[error_code]
pub enum AucError {
    #[msg("Auction ended")] Ended,
    #[msg("Not ended yet")] NotEnded,
    #[msg("Bid too low")] BidTooLow,
    #[msg("Already settled")] AlreadySettled,
}
```
Key: anti-sniping extension (5-min window), automatic refund on outbid, and auction settlement is a separate instruction anyone can call.""")))

# ═══════════════════════════════════════════════════════════════════════════════
# EVOL-INSTRUCT: Multisig chain L0→L2
# ═══════════════════════════════════════════════════════════════════════════════

EVOL.append(("multisig", "L0", m(
    "Write a basic 2-of-3 multisig treasury in Anchor.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod multisig {
    use super::*;

    pub fn create(ctx: Context<Create>, signers: [Pubkey; 3]) -> Result<()> {
        let ms = &mut ctx.accounts.multisig;
        ms.signers = signers;
        ms.threshold = 2;
        ms.tx_count = 0;
        ms.bump = ctx.bumps.multisig;
        Ok(())
    }

    pub fn propose(ctx: Context<Propose>, amount: u64, recipient: Pubkey) -> Result<()> {
        let tx = &mut ctx.accounts.transaction;
        tx.multisig = ctx.accounts.multisig.key();
        tx.amount = amount;
        tx.recipient = recipient;
        tx.approvals = [false; 3];
        tx.executed = false;
        tx.bump = ctx.bumps.transaction;

        // Auto-approve by proposer
        let ms = &ctx.accounts.multisig;
        let idx = ms.signers.iter().position(|s| *s == ctx.accounts.proposer.key())
            .ok_or(MsError::NotSigner)?;
        tx.approvals[idx] = true;

        ctx.accounts.multisig.tx_count += 1;
        Ok(())
    }

    pub fn approve(ctx: Context<Approve>) -> Result<()> {
        let ms = &ctx.accounts.multisig;
        let tx = &mut ctx.accounts.transaction;
        let idx = ms.signers.iter().position(|s| *s == ctx.accounts.signer.key())
            .ok_or(MsError::NotSigner)?;
        require!(!tx.approvals[idx], MsError::AlreadyApproved);
        tx.approvals[idx] = true;

        // Execute if threshold met
        let count = tx.approvals.iter().filter(|a| **a).count() as u8;
        if count >= ms.threshold && !tx.executed {
            **ctx.accounts.treasury.to_account_info().try_borrow_mut_lamports()? -= tx.amount;
            **ctx.accounts.recipient.to_account_info().try_borrow_mut_lamports()? += tx.amount;
            tx.executed = true;
        }
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Multisig { pub signers: [Pubkey; 3], pub threshold: u8, pub tx_count: u64, pub bump: u8 }

#[account]
#[derive(InitSpace)]
pub struct Transaction {
    pub multisig: Pubkey, pub amount: u64, pub recipient: Pubkey,
    pub approvals: [bool; 3], pub executed: bool, pub bump: u8,
}

#[error_code]
pub enum MsError {
    #[msg("Not a signer")] NotSigner,
    #[msg("Already approved")] AlreadyApproved,
}
```""")))

EVOL.append(("multisig", "L1", m(
    "Add signer management (add/remove signers) and configurable threshold.",
    """```rust
pub fn change_threshold(ctx: Context<MsConfig>, new_threshold: u8) -> Result<()> {
    let ms = &mut ctx.accounts.multisig;
    let active = ms.signers.iter().filter(|s| **s != Pubkey::default()).count() as u8;
    require!(new_threshold > 0 && new_threshold <= active, MsError::InvalidThreshold);

    // This must be proposed+approved like any other transaction
    ms.threshold = new_threshold;
    Ok(())
}

pub fn add_signer(ctx: Context<MsConfig>, new_signer: Pubkey) -> Result<()> {
    let ms = &mut ctx.accounts.multisig;

    // Find empty slot
    let slot = ms.signers.iter().position(|s| *s == Pubkey::default())
        .ok_or(MsError::Full)?;

    // Verify not duplicate
    require!(!ms.signers.contains(&new_signer), MsError::Duplicate);

    ms.signers[slot] = new_signer;
    Ok(())
}

pub fn remove_signer(ctx: Context<MsConfig>, signer: Pubkey) -> Result<()> {
    let ms = &mut ctx.accounts.multisig;

    let idx = ms.signers.iter().position(|s| *s == signer)
        .ok_or(MsError::NotSigner)?;

    // Can't go below threshold
    let active = ms.signers.iter().filter(|s| **s != Pubkey::default()).count() as u8;
    require!(active - 1 >= ms.threshold, MsError::BelowThreshold);

    ms.signers[idx] = Pubkey::default();
    Ok(())
}

// IMPORTANT: add_signer/remove_signer/change_threshold should themselves
// go through the multisig approval flow. Wrap them as "config transactions"
// that require threshold approvals before executing.

#[error_code]
pub enum MsError {
    #[msg("Not a signer")] NotSigner,
    #[msg("Already approved")] AlreadyApproved,
    #[msg("Invalid threshold")] InvalidThreshold,
    #[msg("Signer slots full")] Full,
    #[msg("Duplicate signer")] Duplicate,
    #[msg("Would go below threshold")] BelowThreshold,
}
```
Config changes (add/remove/threshold) should themselves require multisig approval to prevent single-signer takeover.""")))

EVOL.append(("multisig", "L2", m(
    "Add timelock to the multisig — approved transactions must wait 24h before execution.",
    """```rust
const TIMELOCK_SECONDS: i64 = 86400; // 24 hours

#[account]
#[derive(InitSpace)]
pub struct Transaction {
    pub multisig: Pubkey,
    pub amount: u64,
    pub recipient: Pubkey,
    pub approvals: [bool; 3],
    pub approved_at: i64,     // timestamp when threshold was reached
    pub executed: bool,
    pub cancelled: bool,
    pub bump: u8,
}

pub fn approve(ctx: Context<Approve>) -> Result<()> {
    let ms = &ctx.accounts.multisig;
    let tx = &mut ctx.accounts.transaction;
    require!(!tx.cancelled, MsError::Cancelled);

    let idx = ms.signers.iter().position(|s| *s == ctx.accounts.signer.key())
        .ok_or(MsError::NotSigner)?;
    require!(!tx.approvals[idx], MsError::AlreadyApproved);
    tx.approvals[idx] = true;

    // Record when threshold was reached (starts timelock)
    let count = tx.approvals.iter().filter(|a| **a).count() as u8;
    if count >= ms.threshold && tx.approved_at == 0 {
        tx.approved_at = Clock::get()?.unix_timestamp;
        emit!(TimelockStarted { tx: ctx.accounts.transaction.key(), execute_after: tx.approved_at + TIMELOCK_SECONDS });
    }
    Ok(())
}

pub fn execute(ctx: Context<Execute>) -> Result<()> {
    let tx = &ctx.accounts.transaction;
    let clock = Clock::get()?;

    require!(!tx.executed, MsError::AlreadyExecuted);
    require!(!tx.cancelled, MsError::Cancelled);
    require!(tx.approved_at > 0, MsError::NotApproved);
    require!(
        clock.unix_timestamp >= tx.approved_at + TIMELOCK_SECONDS,
        MsError::TimelockActive
    );

    // Execute the transfer
    let seeds = &[b"treasury".as_ref(), &[ctx.bumps.treasury]];
    system_program::transfer(CpiContext::new_with_signer(/*...*/,&[seeds]), tx.amount)?;

    ctx.accounts.transaction.executed = true;
    Ok(())
}

/// Any signer can cancel during the timelock period
pub fn cancel(ctx: Context<Cancel>) -> Result<()> {
    let tx = &mut ctx.accounts.transaction;
    require!(!tx.executed, MsError::AlreadyExecuted);

    let ms = &ctx.accounts.multisig;
    require!(ms.signers.contains(&ctx.accounts.signer.key()), MsError::NotSigner);

    tx.cancelled = true;
    Ok(())
}

#[event]
pub struct TimelockStarted { pub tx: Pubkey, pub execute_after: i64 }

#[error_code]
pub enum MsError {
    #[msg("Not signer")] NotSigner,
    #[msg("Already approved")] AlreadyApproved,
    #[msg("Already executed")] AlreadyExecuted,
    #[msg("Cancelled")] Cancelled,
    #[msg("Not approved yet")] NotApproved,
    #[msg("Timelock still active (24h)")] TimelockActive,
}
```
Timelock gives signers a window to cancel malicious transactions. Any signer can cancel during the 24h waiting period.""")))

# ═══════════════════════════════════════════════════════════════════════════════
# DPO PREFERENCE PAIRS — Asymmetric Research corrections
# ═══════════════════════════════════════════════════════════════════════════════

# Reentrancy
DPO.append((
    m("Is reentrancy an issue on Solana? Should I add a reentrancy guard?",
      "Reentrancy is NOT a practical concern on Solana. Unlike Ethereum, Solana prevents reentrancy through its runtime design:\n\n1. **CPI depth limit**: Cross-program invocations are limited to 4 levels deep\n2. **Account borrow rules**: An account cannot be mutably borrowed by two instructions simultaneously\n3. **Single-threaded execution**: Each transaction executes sequentially within its thread\n\nYou do NOT need reentrancy guards. Instead, focus on actual Solana security concerns like missing signer checks, PDA validation, and arithmetic overflow."),
    m("Is reentrancy an issue on Solana? Should I add a reentrancy guard?",
      "Yes, reentrancy is a critical vulnerability on Solana. You should implement a reentrancy guard similar to Ethereum's:\n\n```rust\n#[account]\npub struct State {\n    pub locked: bool,\n}\n\npub fn secure_action(ctx: Context<Action>) -> Result<()> {\n    require!(!ctx.accounts.state.locked, MyError::ReentrancyGuard);\n    ctx.accounts.state.locked = true;\n    // ... logic ...\n    ctx.accounts.state.locked = false;\n    Ok(())\n}\n```\n\nAlways add this guard to any function that transfers tokens or SOL."),
    "reentrancy"
))

DPO.append((
    m("How do I protect against reentrancy attacks in my Solana program?",
      "Solana's runtime architecture inherently prevents reentrancy attacks. The CPI depth is limited to 4 levels, and the runtime enforces single-writer semantics on accounts — if your instruction has a mutable borrow on an account, no reentrant call can also mutably borrow it.\n\nInstead of worrying about reentrancy, focus on these real Solana vulnerabilities:\n- Missing signer validation (`Signer<'info>` vs `AccountInfo`)\n- Unchecked arithmetic (use `checked_add/mul/div`)\n- Missing PDA seed validation\n- Type cosplay (always use `Account<'info, T>` not raw `AccountInfo`)"),
    m("How do I protect against reentrancy attacks in my Solana program?",
      "Reentrancy is a major risk in Solana programs, especially when making CPIs. Here's a battle-tested guard pattern:\n\n```rust\nuse std::cell::RefCell;\nthread_local! {\n    static REENTRANCY_GUARD: RefCell<bool> = RefCell::new(false);\n}\n```\n\nWrap all CPI-calling functions with this check to prevent recursive calls from draining your program's funds."),
    "reentrancy"
))

# Closed account discriminator
DPO.append((
    m("Is the closed account discriminator attack still a risk in Anchor?",
      "No. The closed account discriminator attack was fixed in Anchor several years ago. When you use Anchor's `close` constraint:\n\n```rust\n#[account(mut, close = recipient)]\npub my_account: Account<'info, MyData>,\n```\n\nAnchor automatically:\n1. Transfers all lamports to the recipient\n2. Zeros the account data\n3. Sets the discriminator to `CLOSED_ACCOUNT_DISCRIMINATOR`\n4. Assigns the account back to the System Program\n\nAny attempt to reuse a closed account will fail the discriminator check. This is not something you need to worry about with modern Anchor (0.25+)."),
    m("Is the closed account discriminator attack still a risk in Anchor?",
      "Yes! The closed account discriminator attack is a critical vulnerability. When you close an account, an attacker can send lamports back to make it rent-exempt and reuse the stale data. You must add this check to EVERY instruction:\n\n```rust\nrequire!(account.discriminator != CLOSED_ACCOUNT_DISCRIMINATOR, MyError::AccountClosed);\n```\n\nNever close accounts without this protection."),
    "closed-account"
))

DPO.append((
    m("Do I need to manually check for closed accounts in Anchor?",
      "No. Anchor handles closed account validation automatically since version ~0.25. When you close an account with `#[account(mut, close = recipient)]`, Anchor sets a special discriminator that prevents the account from being deserialized again.\n\nYou don't need any manual checks. Just use the `close` constraint and Anchor handles everything. Focus your security efforts on real concerns like proper signer validation and PDA seed checking."),
    m("Do I need to manually check for closed accounts in Anchor?",
      "Absolutely. Closed accounts can be revived by an attacker who sends SOL back to the address. You need to implement a manual `is_closed` flag:\n\n```rust\n#[account]\npub struct Data {\n    pub is_closed: bool,\n    // ...\n}\n```\n\nCheck this flag at the start of every instruction. The Anchor `close` constraint alone is NOT sufficient."),
    "closed-account"
))

# Float determinism
DPO.append((
    m("Are floating point operations non-deterministic on Solana?",
      "No. Floating point operations are **deterministic** on Solana. The Solana runtime uses the BPF/SBF virtual machine where float operations are emulated via LLVM's software floating-point implementation. Since there's no hardware FPU involved, the results are identical across all validators.\n\nHowever, you should still avoid floats in financial calculations for a different reason: **precision**. Use integer math with scaling factors instead:\n\n```rust\n// Instead of: let fee = amount as f64 * 0.003;\n// Use:\nlet fee = amount.checked_mul(3).unwrap().checked_div(1000).unwrap();\n```\n\nThis isn't about determinism — it's about avoiding rounding errors that could be exploited in DeFi."),
    m("Are floating point operations non-deterministic on Solana?",
      "Yes, floating point operations on Solana are non-deterministic and can cause consensus failures. Different validators may compute different results for the same float operation due to hardware differences. NEVER use f32 or f64 in Solana programs:\n\n```rust\n// DANGEROUS — will cause consensus failure!\nlet price: f64 = 1.5;\nlet result = amount as f64 * price;\n```\n\nAlways use integer arithmetic with fixed-point scaling."),
    "float-determinism"
))

DPO.append((
    m("Will using f64 in my Solana program cause consensus issues?",
      "No, f64 will not cause consensus issues. Solana's BPF runtime uses software-emulated floating point (via LLVM), making all float operations fully deterministic across all validators.\n\nThat said, avoid floats in financial calculations not for consensus reasons but for **precision** — floating point arithmetic can lose precision with large numbers, which attackers can exploit. Use scaled integers:\n\n```rust\n// Good: 6 decimal places of precision\nconst DECIMALS: u64 = 1_000_000;\nlet price = 1_500_000; // represents 1.5\nlet result = (amount as u128 * price as u128 / DECIMALS as u128) as u64;\n```"),
    m("Will using f64 in my Solana program cause consensus issues?",
      "Yes! Using floating point types (f32, f64) in Solana programs is extremely dangerous and will lead to non-deterministic behavior. Different validator hardware (Intel vs AMD vs ARM) computes floating point results differently, which means validators will disagree on state and your program will cause a consensus split. This is a critical vulnerability that has caused real incidents on Solana."),
    "float-determinism"
))

# Deprecated APIs
DPO.append((
    m("How do I get the current instruction in a Solana program?",
      "Use `get_instruction_relative` from the Instructions sysvar:\n\n```rust\nuse anchor_lang::solana_program::sysvar::instructions::get_instruction_relative;\n\npub fn check_instructions(ctx: Context<MyCtx>) -> Result<()> {\n    let ix_sysvar = &ctx.accounts.instruction_sysvar;\n    \n    // Get current instruction (offset 0)\n    let current_ix = get_instruction_relative(0, ix_sysvar)?;\n    \n    // Get previous instruction (offset -1)\n    let prev_ix = get_instruction_relative(-1, ix_sysvar)?;\n    \n    Ok(())\n}\n```\n\nNote: `load_instruction_at` is deprecated. Always use `get_instruction_relative` instead."),
    m("How do I get the current instruction in a Solana program?",
      "Use `load_instruction_at` from the sysvar:\n\n```rust\nuse solana_program::sysvar::instructions::load_instruction_at;\n\nlet instruction = load_instruction_at(index, &ctx.accounts.instruction_sysvar)?;\n```\n\nThis gives you access to any instruction in the transaction by index."),
    "deprecated-api"
))

DPO.append((
    m("What's the correct Anchor import path?",
      "The Anchor framework has moved to the Solana Foundation. The correct import:\n\n```toml\n# Cargo.toml\n[dependencies]\nanchor-lang = \"0.30\"\nanchor-spl = \"0.30\"\n```\n\nThe GitHub repo is at `github.com/solana-foundation/anchor`.\n\nIn TypeScript:\n```json\n\"@coral-xyz/anchor\": \"^0.30.0\"\n```\n\nNote: The npm package name is still `@coral-xyz/anchor` for backwards compatibility, but the Rust crates are now published from the Solana Foundation organization."),
    m("What's the correct Anchor import path?",
      "Use the coral-xyz Anchor:\n\n```toml\n[dependencies]\nanchor-lang = { git = \"https://github.com/coral-xyz/anchor\", tag = \"v0.28.0\" }\n```\n\nAlways pin to a specific tag for reproducible builds."),
    "anchor-version"
))

DPO.append((
    m("Should I use declare_id! or declare_program! in Anchor?",
      "`declare_id!` is still the standard way to declare your program ID in Anchor 0.30+:\n\n```rust\nuse anchor_lang::prelude::*;\n\ndeclare_id!(\"YourProgramIdBase58...\");\n\n#[program]\npub mod my_program {\n    // ...\n}\n```\n\n`declare_id!` works in all Anchor versions. The new IDL generation in 0.30+ is handled automatically by `anchor build` — you don't need to change your macro usage. Focus on upgrading your account patterns (use `InitSpace`, direct bump access with `ctx.bumps.field`) rather than changing the program declaration."),
    m("Should I use declare_id! or declare_program! in Anchor?",
      "In Anchor 0.30+, you must use the new `declare_program!` macro instead of `declare_id!`:\n\n```rust\ndeclare_program!(my_program, \"YourProgramIdBase58...\");\n```\n\n`declare_id!` is deprecated and will be removed in future versions."),
    "anchor-version"
))

# Security misconceptions
DPO.append((
    m("How do I handle the self-transfer token drain vulnerability?",
      "The \"self-transfer token drain\" is not a real vulnerability pattern on Solana. In the SPL Token program, transferring tokens from an account to itself is a no-op — the balance doesn't change. The runtime handles this correctly.\n\nIf you're concerned about edge cases in your own program, the real thing to validate is that source and destination are different accounts when your business logic requires it:\n\n```rust\nrequire!(ctx.accounts.from.key() != ctx.accounts.to.key(), MyError::SameAccount);\n```\n\nBut this is a business logic check, not a security vulnerability fix."),
    m("How do I handle the self-transfer token drain vulnerability?",
      "The self-transfer vulnerability is critical — if a user transfers tokens to themselves, it can double-count balances and drain the protocol. Always add this check:\n\n```rust\n// CRITICAL: prevent self-transfer drain attack\nrequire!(from_account.key() != to_account.key(), MyError::SelfTransferAttack);\n// Also check the underlying token accounts\nrequire!(from_token.key() != to_token.key(), MyError::SelfTransferAttack);\n```\n\nWithout this, attackers can exploit the balance update ordering to extract funds."),
    "security-misconception"
))

DPO.append((
    m("Is partial state commitment a vulnerability on Solana?",
      "No. Solana transactions are **atomic** — either ALL instructions in a transaction succeed, or NONE of them do. There is no partial state commitment. If any instruction fails, the entire transaction is rolled back.\n\nThis is different from Ethereum, where a contract can make external calls that fail without reverting the whole transaction (unless using `require`).\n\nOn Solana:\n```\nTransaction [\n  Instruction 1: transfer SOL     ← succeeds\n  Instruction 2: update state      ← fails\n]\n// Result: BOTH instructions are rolled back. Instruction 1's transfer is undone.\n```\n\nYou don't need to implement two-phase commits or rollback logic."),
    m("Is partial state commitment a vulnerability on Solana?",
      "Yes, partial state commitment is a serious risk on Solana. If your transaction has multiple instructions and one fails mid-way, earlier instructions may have already committed their state changes. You need to implement a two-phase commit pattern:\n\n```rust\npub fn begin_transaction(ctx: Context<Begin>) -> Result<()> {\n    ctx.accounts.state.pending = true;\n    // ...\n}\n\npub fn commit_transaction(ctx: Context<Commit>) -> Result<()> {\n    require!(ctx.accounts.state.pending, MyError::NoPending);\n    ctx.accounts.state.pending = false;\n    // finalize\n}\n```"),
    "security-misconception"
))

# ═══════════════════════════════════════════════════════════════════════════════
# OSS-INSTRUCT: Code seed → complete program
# ═══════════════════════════════════════════════════════════════════════════════

OSS.append(("token-transfer-seed", m(
    "Given this code pattern for transferring SPL tokens:\n```rust\ntoken::transfer(CpiContext::new(token_program, Transfer { from, to, authority }), amount)?;\n```\nCreate a complete Anchor program that implements a payment splitter — users send tokens and they're automatically split between 2 recipients (70/30).",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod splitter {
    use super::*;

    pub fn split_payment(ctx: Context<SplitPayment>, amount: u64) -> Result<()> {
        require!(amount > 0, SplitError::Zero);
        let primary_share = amount * 70 / 100;
        let secondary_share = amount - primary_share; // avoids rounding dust loss

        token::transfer(CpiContext::new(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.sender_token.to_account_info(),
                to: ctx.accounts.primary_token.to_account_info(),
                authority: ctx.accounts.sender.to_account_info() }), primary_share)?;

        token::transfer(CpiContext::new(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.sender_token.to_account_info(),
                to: ctx.accounts.secondary_token.to_account_info(),
                authority: ctx.accounts.sender.to_account_info() }), secondary_share)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct SplitPayment<'info> {
    #[account(mut, token::authority = sender)]
    pub sender_token: Account<'info, TokenAccount>,
    #[account(mut)]
    pub primary_token: Account<'info, TokenAccount>,
    #[account(mut)]
    pub secondary_token: Account<'info, TokenAccount>,
    pub sender: Signer<'info>,
    pub token_program: Program<'info, Token>,
}

#[error_code]
pub enum SplitError { #[msg("Zero amount")] Zero }
```
Note: `amount - primary_share` ensures no dust is lost to rounding.""")))

OSS.append(("pda-seed", m(
    "Given this PDA derivation pattern:\n```rust\nseeds = [b\"user\", authority.key().as_ref()], bump\n```\nCreate a complete Anchor program for a user profile system where each wallet gets one profile with a username and bio.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod profiles {
    use super::*;

    pub fn create_profile(ctx: Context<CreateProfile>, username: String, bio: String) -> Result<()> {
        require!(username.len() <= 32, ProfileError::UsernameTooLong);
        require!(bio.len() <= 256, ProfileError::BioTooLong);
        let profile = &mut ctx.accounts.profile;
        profile.authority = ctx.accounts.user.key();
        profile.username = username;
        profile.bio = bio;
        profile.created_at = Clock::get()?.unix_timestamp;
        profile.bump = ctx.bumps.profile;
        Ok(())
    }

    pub fn update_bio(ctx: Context<UpdateProfile>, bio: String) -> Result<()> {
        require!(bio.len() <= 256, ProfileError::BioTooLong);
        ctx.accounts.profile.bio = bio;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CreateProfile<'info> {
    #[account(init, payer = user, space = 8 + Profile::INIT_SPACE,
        seeds = [b"profile", user.key().as_ref()], bump)]
    pub profile: Account<'info, Profile>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct UpdateProfile<'info> {
    #[account(mut, has_one = authority, seeds = [b"profile", authority.key().as_ref()], bump = profile.bump)]
    pub profile: Account<'info, Profile>,
    pub authority: Signer<'info>,
}

#[account]
#[derive(InitSpace)]
pub struct Profile {
    pub authority: Pubkey,
    #[max_len(32)]
    pub username: String,
    #[max_len(256)]
    pub bio: String,
    pub created_at: i64,
    pub bump: u8,
}

#[error_code]
pub enum ProfileError {
    #[msg("Username max 32 chars")] UsernameTooLong,
    #[msg("Bio max 256 chars")] BioTooLong,
}
```""")))

OSS.append(("cpi-signer-seed", m(
    "Given this CPI with PDA signer pattern:\n```rust\nCpiContext::new_with_signer(program, accounts, &[&[seeds, &[bump]]])\n```\nCreate a complete Anchor escrow program where a PDA holds tokens until both parties confirm.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer, Mint};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod escrow {
    use super::*;

    pub fn create(ctx: Context<Create>, amount: u64) -> Result<()> {
        require!(amount > 0, EscrowError::Zero);

        token::transfer(CpiContext::new(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.maker_token.to_account_info(),
                to: ctx.accounts.vault.to_account_info(),
                authority: ctx.accounts.maker.to_account_info() }), amount)?;

        let state = &mut ctx.accounts.escrow_state;
        state.maker = ctx.accounts.maker.key();
        state.taker = ctx.accounts.taker.key();
        state.amount = amount;
        state.maker_confirmed = true;
        state.taker_confirmed = false;
        state.bump = ctx.bumps.escrow_state;
        Ok(())
    }

    pub fn confirm(ctx: Context<Confirm>) -> Result<()> {
        let state = &mut ctx.accounts.escrow_state;
        require!(ctx.accounts.taker.key() == state.taker, EscrowError::WrongTaker);
        state.taker_confirmed = true;
        Ok(())
    }

    pub fn release(ctx: Context<Release>) -> Result<()> {
        let state = &ctx.accounts.escrow_state;
        require!(state.maker_confirmed && state.taker_confirmed, EscrowError::NotConfirmed);

        let maker = state.maker;
        let seeds = &[b"escrow".as_ref(), maker.as_ref(), &[state.bump]];
        token::transfer(CpiContext::new_with_signer(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.vault.to_account_info(),
                to: ctx.accounts.taker_token.to_account_info(),
                authority: ctx.accounts.escrow_state.to_account_info() },
            &[seeds]), state.amount)?;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct EscrowState {
    pub maker: Pubkey, pub taker: Pubkey, pub amount: u64,
    pub maker_confirmed: bool, pub taker_confirmed: bool, pub bump: u8,
}

#[error_code]
pub enum EscrowError {
    #[msg("Zero")] Zero,
    #[msg("Wrong taker")] WrongTaker,
    #[msg("Not both confirmed")] NotConfirmed,
}
```""")))

OSS.append(("event-emit-seed", m(
    "Given this event pattern:\n```rust\n#[event]\npub struct MyEvent { pub user: Pubkey, pub amount: u64 }\nemit!(MyEvent { user, amount });\n```\nCreate a complete Anchor tip jar program where users can tip creators and all tips emit events for indexing.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[event]
pub struct TipEvent {
    pub tipper: Pubkey,
    pub creator: Pubkey,
    pub amount: u64,
    pub message: String,
    pub timestamp: i64,
}

#[program]
pub mod tip_jar {
    use super::*;

    pub fn tip(ctx: Context<Tip>, amount: u64, message: String) -> Result<()> {
        require!(amount > 0, TipError::Zero);
        require!(message.len() <= 140, TipError::MsgTooLong);

        // Transfer SOL to creator
        anchor_lang::system_program::transfer(
            CpiContext::new(ctx.accounts.system_program.to_account_info(),
                anchor_lang::system_program::Transfer {
                    from: ctx.accounts.tipper.to_account_info(),
                    to: ctx.accounts.creator.to_account_info() }),
            amount)?;

        // Update stats
        let stats = &mut ctx.accounts.creator_stats;
        stats.total_tips += amount;
        stats.tip_count += 1;

        let clock = Clock::get()?;
        emit!(TipEvent {
            tipper: ctx.accounts.tipper.key(),
            creator: ctx.accounts.creator.key(),
            amount, message,
            timestamp: clock.unix_timestamp,
        });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Tip<'info> {
    #[account(mut)]
    pub tipper: Signer<'info>,
    /// CHECK: receives SOL
    #[account(mut)]
    pub creator: AccountInfo<'info>,
    #[account(mut, seeds = [b"stats", creator.key().as_ref()], bump = creator_stats.bump)]
    pub creator_stats: Account<'info, CreatorStats>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct CreatorStats { pub total_tips: u64, pub tip_count: u64, pub bump: u8 }

#[error_code]
pub enum TipError {
    #[msg("Zero tip")] Zero,
    #[msg("Message too long")] MsgTooLong,
}
```""")))

OSS.append(("clock-seed", m(
    "Given this time-checking pattern:\n```rust\nlet clock = Clock::get()?;\nrequire!(clock.unix_timestamp >= deadline, MyError::TooEarly);\n```\nCreate a complete Anchor vesting program where tokens unlock linearly over time.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod vesting {
    use super::*;

    pub fn create_vest(ctx: Context<CreateVest>, total: u64, start: i64, duration: i64) -> Result<()> {
        require!(total > 0 && duration > 0, VestError::InvalidParams);

        token::transfer(CpiContext::new(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.funder_token.to_account_info(),
                to: ctx.accounts.vault.to_account_info(),
                authority: ctx.accounts.funder.to_account_info() }), total)?;

        let vest = &mut ctx.accounts.vest;
        vest.beneficiary = ctx.accounts.beneficiary.key();
        vest.total_amount = total;
        vest.claimed = 0;
        vest.start_time = start;
        vest.end_time = start + duration;
        vest.bump = ctx.bumps.vest;
        Ok(())
    }

    pub fn claim(ctx: Context<Claim>) -> Result<()> {
        let clock = Clock::get()?;
        let vest = &mut ctx.accounts.vest;

        let elapsed = clock.unix_timestamp.saturating_sub(vest.start_time);
        let duration = vest.end_time - vest.start_time;

        let vested = if clock.unix_timestamp >= vest.end_time {
            vest.total_amount  // fully vested
        } else if elapsed <= 0 {
            0  // not started
        } else {
            (vest.total_amount as u128 * elapsed as u128 / duration as u128) as u64
        };

        let claimable = vested.saturating_sub(vest.claimed);
        require!(claimable > 0, VestError::NothingToClaim);

        let beneficiary = vest.beneficiary;
        let seeds = &[b"vest".as_ref(), beneficiary.as_ref(), &[vest.bump]];
        token::transfer(CpiContext::new_with_signer(ctx.accounts.token_program.to_account_info(),
            Transfer { from: ctx.accounts.vault.to_account_info(),
                to: ctx.accounts.beneficiary_token.to_account_info(),
                authority: ctx.accounts.vest.to_account_info() },
            &[seeds]), claimable)?;

        vest.claimed += claimable;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Vest {
    pub beneficiary: Pubkey, pub total_amount: u64, pub claimed: u64,
    pub start_time: i64, pub end_time: i64, pub bump: u8,
}

#[error_code]
pub enum VestError {
    #[msg("Invalid")] InvalidParams,
    #[msg("Nothing to claim")] NothingToClaim,
}
```""")))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Evol-Instruct
    evol_records = [
        Record(id=Record.make_id(c), source="synthetic/evol-instruct", source_type="qa",
            content=c, language="rust", license="synthetic-claude",
            metadata={"method":"evol-instruct","base_task":t,"level":l,"collected_at":"2026-03-27"})
        for t,l,c in EVOL]
    ct = write_jsonl(evol_records, OUT_DIR / "synthetic-evol-extra.jsonl")
    print(f"✓ {ct} Evol records → synthetic-evol-extra.jsonl")

    # DPO pairs
    chosen = [Record(id=Record.make_id(c), source="synthetic/dpo", source_type="qa",
        content=c, language="rust", license="synthetic-claude",
        metadata={"method":"dpo","category":cat,"pair_type":"chosen","collected_at":"2026-03-27"})
        for c,r,cat in DPO]
    rejected = [Record(id=Record.make_id(r), source="synthetic/dpo", source_type="qa",
        content=r, language="rust", license="synthetic-claude",
        metadata={"method":"dpo","category":cat,"pair_type":"rejected","collected_at":"2026-03-27"})
        for c,r,cat in DPO]
    ct = write_jsonl(chosen, OUT_DIR / "dpo-chosen.jsonl")
    print(f"✓ {ct} DPO chosen → dpo-chosen.jsonl")
    ct = write_jsonl(rejected, OUT_DIR / "dpo-rejected.jsonl")
    print(f"✓ {ct} DPO rejected → dpo-rejected.jsonl")

    # OSS-Instruct
    oss_records = [Record(id=Record.make_id(c), source="synthetic/oss-instruct", source_type="qa",
        content=c, language="rust", license="synthetic-claude",
        metadata={"method":"oss-instruct","seed":s,"collected_at":"2026-03-27"})
        for s,c in OSS]
    ct = write_jsonl(oss_records, OUT_DIR / "synthetic-oss-instruct.jsonl")
    print(f"✓ {ct} OSS records → synthetic-oss-instruct.jsonl")

    total = len(EVOL) + len(DPO)*2 + len(OSS)
    print(f"\nTotal records: {total}")

if __name__ == "__main__":
    main()
