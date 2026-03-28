#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 3: Evol-Instruct chains, DPO pairs, OSS-Instruct.

Target: ~300 pairs from this file.
"""
import json, sys
from pathlib import Path
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


def rec(content, method, category=""):
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


EVOL = []
DPO_CHOSEN = []
DPO_REJECTED = []
OSS = []

# ═══════════════════════════════════════════════════════════════════════════════
# EVOL-INSTRUCT: Progressive complexity chains
# Each chain has L0 (basic) → L1 (intermediate) → L2 (advanced)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Chain 1: Token Staking ──────────────────────────────────────────────────

EVOL.append(("staking-L0", m(
    "Write a basic Anchor program that lets users deposit SOL into a vault PDA.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod sol_vault {
    use super::*;

    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.user.key(),
            &ctx.accounts.vault.key(),
            amount,
        );
        anchor_lang::solana_program::program::invoke(
            &ix,
            &[
                ctx.accounts.user.to_account_info(),
                ctx.accounts.vault.to_account_info(),
            ],
        )?;

        let vault_state = &mut ctx.accounts.vault_state;
        vault_state.total_deposited = vault_state.total_deposited
            .checked_add(amount).unwrap();

        Ok(())
    }
}

#[derive(Accounts)]
pub struct Deposit<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    /// CHECK: PDA vault that holds SOL
    #[account(
        mut,
        seeds = [b"vault"],
        bump,
    )]
    pub vault: SystemAccount<'info>,
    #[account(
        init_if_needed,
        payer = user,
        space = 8 + VaultState::INIT_SPACE,
        seeds = [b"vault-state"],
        bump,
    )]
    pub vault_state: Account<'info, VaultState>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct VaultState {
    pub total_deposited: u64,
    pub bump: u8,
}
```""")))

EVOL.append(("staking-L1", m(
    "Extend the SOL vault to track per-user deposits, allow withdrawals, and add a minimum deposit requirement.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

const MIN_DEPOSIT: u64 = 100_000_000; // 0.1 SOL

#[program]
pub mod sol_vault {
    use super::*;

    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        require!(amount >= MIN_DEPOSIT, VaultError::BelowMinDeposit);

        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.user.key(),
            &ctx.accounts.vault.key(),
            amount,
        );
        anchor_lang::solana_program::program::invoke(
            &ix,
            &[
                ctx.accounts.user.to_account_info(),
                ctx.accounts.vault.to_account_info(),
            ],
        )?;

        let user_deposit = &mut ctx.accounts.user_deposit;
        user_deposit.owner = ctx.accounts.user.key();
        user_deposit.amount = user_deposit.amount
            .checked_add(amount).ok_or(VaultError::MathOverflow)?;
        user_deposit.last_deposit_time = Clock::get()?.unix_timestamp;

        let vault_state = &mut ctx.accounts.vault_state;
        vault_state.total_deposited = vault_state.total_deposited
            .checked_add(amount).ok_or(VaultError::MathOverflow)?;
        vault_state.depositor_count = vault_state.depositor_count
            .checked_add(1).ok_or(VaultError::MathOverflow)?;

        emit!(DepositEvent {
            user: ctx.accounts.user.key(),
            amount,
            total: user_deposit.amount,
        });
        Ok(())
    }

    pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
        let user_deposit = &mut ctx.accounts.user_deposit;
        require!(user_deposit.amount >= amount, VaultError::InsufficientBalance);

        // Transfer SOL from PDA vault
        let vault = &ctx.accounts.vault;
        **vault.to_account_info().try_borrow_mut_lamports()? -= amount;
        **ctx.accounts.user.to_account_info().try_borrow_mut_lamports()? += amount;

        user_deposit.amount = user_deposit.amount
            .checked_sub(amount).ok_or(VaultError::MathOverflow)?;

        let vault_state = &mut ctx.accounts.vault_state;
        vault_state.total_deposited = vault_state.total_deposited
            .checked_sub(amount).ok_or(VaultError::MathOverflow)?;

        emit!(WithdrawEvent { user: ctx.accounts.user.key(), amount });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Deposit<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    /// CHECK: PDA vault
    #[account(mut, seeds = [b"vault"], bump)]
    pub vault: SystemAccount<'info>,
    #[account(mut, seeds = [b"vault-state"], bump = vault_state.bump)]
    pub vault_state: Account<'info, VaultState>,
    #[account(
        init_if_needed,
        payer = user,
        space = 8 + UserDeposit::INIT_SPACE,
        seeds = [b"deposit", user.key().as_ref()],
        bump,
    )]
    pub user_deposit: Account<'info, UserDeposit>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    /// CHECK: PDA vault
    #[account(mut, seeds = [b"vault"], bump)]
    pub vault: SystemAccount<'info>,
    #[account(mut, seeds = [b"vault-state"], bump = vault_state.bump)]
    pub vault_state: Account<'info, VaultState>,
    #[account(
        mut,
        seeds = [b"deposit", user.key().as_ref()],
        bump = user_deposit.bump,
        has_one = owner @ VaultError::Unauthorized,
    )]
    pub user_deposit: Account<'info, UserDeposit>,
}

// Rename to match has_one:
// Note: `has_one = owner` checks user_deposit.owner == owner.key()
// We need the field name and account name to match

#[account]
#[derive(InitSpace)]
pub struct VaultState {
    pub total_deposited: u64,
    pub depositor_count: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct UserDeposit {
    pub owner: Pubkey,
    pub amount: u64,
    pub last_deposit_time: i64,
    pub bump: u8,
}

#[event]
pub struct DepositEvent { pub user: Pubkey, pub amount: u64, pub total: u64 }
#[event]
pub struct WithdrawEvent { pub user: Pubkey, pub amount: u64 }

#[error_code]
pub enum VaultError {
    #[msg("Deposit below minimum")] BelowMinDeposit,
    #[msg("Insufficient balance")] InsufficientBalance,
    #[msg("Math overflow")] MathOverflow,
    #[msg("Unauthorized")] Unauthorized,
}
```""")))

EVOL.append(("staking-L2", m(
    "Add time-based staking rewards to the vault: a configurable reward rate, reward claiming, lockup periods, and an admin pause mechanism.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod staking_vault {
    use super::*;

    pub fn initialize(
        ctx: Context<Initialize>,
        reward_rate: u64,
        lockup_duration: i64,
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;
        config.admin = ctx.accounts.admin.key();
        config.reward_rate = reward_rate; // lamports per second per SOL staked
        config.lockup_duration = lockup_duration;
        config.total_staked = 0;
        config.is_paused = false;
        config.bump = ctx.bumps.config;
        Ok(())
    }

    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        let config = &ctx.accounts.config;
        require!(!config.is_paused, StakeError::Paused);
        require!(amount > 0, StakeError::ZeroAmount);

        // Claim pending rewards before changing stake
        let user_stake = &mut ctx.accounts.user_stake;
        if user_stake.staked_amount > 0 {
            let pending = calculate_rewards(user_stake, config)?;
            if pending > 0 {
                let vault = &ctx.accounts.vault;
                **vault.to_account_info().try_borrow_mut_lamports()? -= pending;
                **ctx.accounts.user.to_account_info().try_borrow_mut_lamports()? += pending;
                user_stake.rewards_claimed = user_stake.rewards_claimed
                    .checked_add(pending).ok_or(StakeError::MathOverflow)?;
            }
        }

        // Transfer SOL to vault
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.user.key(),
            &ctx.accounts.vault.key(),
            amount,
        );
        anchor_lang::solana_program::program::invoke(
            &ix,
            &[ctx.accounts.user.to_account_info(), ctx.accounts.vault.to_account_info()],
        )?;

        let clock = Clock::get()?;
        user_stake.owner = ctx.accounts.user.key();
        user_stake.staked_amount = user_stake.staked_amount
            .checked_add(amount).ok_or(StakeError::MathOverflow)?;
        user_stake.last_reward_time = clock.unix_timestamp;
        user_stake.lockup_end = clock.unix_timestamp
            .checked_add(config.lockup_duration).ok_or(StakeError::MathOverflow)?;
        user_stake.bump = ctx.bumps.user_stake;

        let config = &mut ctx.accounts.config;
        config.total_staked = config.total_staked
            .checked_add(amount).ok_or(StakeError::MathOverflow)?;

        emit!(StakeEvent { user: ctx.accounts.user.key(), amount, total: user_stake.staked_amount });
        Ok(())
    }

    pub fn unstake(ctx: Context<Unstake>, amount: u64) -> Result<()> {
        let config = &ctx.accounts.config;
        let user_stake = &mut ctx.accounts.user_stake;
        let clock = Clock::get()?;

        require!(user_stake.staked_amount >= amount, StakeError::InsufficientStake);
        require!(clock.unix_timestamp >= user_stake.lockup_end, StakeError::LockupActive);

        // Claim rewards
        let pending = calculate_rewards(user_stake, config)?;
        let total_withdraw = amount.checked_add(pending).ok_or(StakeError::MathOverflow)?;

        let vault = &ctx.accounts.vault;
        **vault.to_account_info().try_borrow_mut_lamports()? -= total_withdraw;
        **ctx.accounts.user.to_account_info().try_borrow_mut_lamports()? += total_withdraw;

        user_stake.staked_amount = user_stake.staked_amount
            .checked_sub(amount).ok_or(StakeError::MathOverflow)?;
        user_stake.last_reward_time = clock.unix_timestamp;
        user_stake.rewards_claimed = user_stake.rewards_claimed
            .checked_add(pending).ok_or(StakeError::MathOverflow)?;

        let config = &mut ctx.accounts.config;
        config.total_staked = config.total_staked
            .checked_sub(amount).ok_or(StakeError::MathOverflow)?;
        Ok(())
    }

    pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
        let config = &ctx.accounts.config;
        require!(!config.is_paused, StakeError::Paused);

        let user_stake = &mut ctx.accounts.user_stake;
        let pending = calculate_rewards(user_stake, config)?;
        require!(pending > 0, StakeError::NoRewards);

        let vault = &ctx.accounts.vault;
        **vault.to_account_info().try_borrow_mut_lamports()? -= pending;
        **ctx.accounts.user.to_account_info().try_borrow_mut_lamports()? += pending;

        user_stake.last_reward_time = Clock::get()?.unix_timestamp;
        user_stake.rewards_claimed = user_stake.rewards_claimed
            .checked_add(pending).ok_or(StakeError::MathOverflow)?;

        emit!(ClaimEvent { user: ctx.accounts.user.key(), amount: pending });
        Ok(())
    }

    pub fn toggle_pause(ctx: Context<AdminAction>) -> Result<()> {
        let config = &mut ctx.accounts.config;
        config.is_paused = !config.is_paused;
        emit!(PauseEvent { is_paused: config.is_paused });
        Ok(())
    }

    pub fn update_reward_rate(ctx: Context<AdminAction>, new_rate: u64) -> Result<()> {
        ctx.accounts.config.reward_rate = new_rate;
        Ok(())
    }
}

fn calculate_rewards(user_stake: &UserStake, config: &StakingConfig) -> Result<u64> {
    let clock = Clock::get()?;
    let elapsed = clock.unix_timestamp
        .checked_sub(user_stake.last_reward_time)
        .ok_or(StakeError::MathOverflow)?;
    if elapsed <= 0 { return Ok(0); }

    let reward = (user_stake.staked_amount as u128)
        .checked_mul(config.reward_rate as u128).ok_or(StakeError::MathOverflow)?
        .checked_mul(elapsed as u128).ok_or(StakeError::MathOverflow)?
        .checked_div(1_000_000_000_u128).ok_or(StakeError::MathOverflow)?; // precision
    Ok(reward as u64)
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(init, payer = admin, space = 8 + StakingConfig::INIT_SPACE, seeds = [b"config"], bump)]
    pub config: Account<'info, StakingConfig>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Stake<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, StakingConfig>,
    /// CHECK: PDA vault
    #[account(mut, seeds = [b"vault"], bump)]
    pub vault: SystemAccount<'info>,
    #[account(
        init_if_needed, payer = user,
        space = 8 + UserStake::INIT_SPACE,
        seeds = [b"stake", user.key().as_ref()], bump,
    )]
    pub user_stake: Account<'info, UserStake>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Unstake<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, StakingConfig>,
    /// CHECK: PDA vault
    #[account(mut, seeds = [b"vault"], bump)]
    pub vault: SystemAccount<'info>,
    #[account(mut, seeds = [b"stake", user.key().as_ref()], bump = user_stake.bump, has_one = owner)]
    pub user_stake: Account<'info, UserStake>,
}

#[derive(Accounts)]
pub struct ClaimRewards<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, StakingConfig>,
    /// CHECK: PDA vault
    #[account(mut, seeds = [b"vault"], bump)]
    pub vault: SystemAccount<'info>,
    #[account(mut, seeds = [b"stake", user.key().as_ref()], bump = user_stake.bump)]
    pub user_stake: Account<'info, UserStake>,
}

#[derive(Accounts)]
pub struct AdminAction<'info> {
    pub admin: Signer<'info>,
    #[account(mut, seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, StakingConfig>,
}

#[account]
#[derive(InitSpace)]
pub struct StakingConfig {
    pub admin: Pubkey,
    pub reward_rate: u64,
    pub lockup_duration: i64,
    pub total_staked: u64,
    pub is_paused: bool,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct UserStake {
    pub owner: Pubkey,
    pub staked_amount: u64,
    pub last_reward_time: i64,
    pub lockup_end: i64,
    pub rewards_claimed: u64,
    pub bump: u8,
}

#[event] pub struct StakeEvent { pub user: Pubkey, pub amount: u64, pub total: u64 }
#[event] pub struct ClaimEvent { pub user: Pubkey, pub amount: u64 }
#[event] pub struct PauseEvent { pub is_paused: bool }

#[error_code]
pub enum StakeError {
    #[msg("Program is paused")] Paused,
    #[msg("Zero amount")] ZeroAmount,
    #[msg("Insufficient stake")] InsufficientStake,
    #[msg("Lockup period active")] LockupActive,
    #[msg("No rewards to claim")] NoRewards,
    #[msg("Math overflow")] MathOverflow,
}
```""")))


# ── Chain 2: NFT Minting ──────────────────────────────────────────────────

EVOL.append(("nft-L0", m(
    "Write a basic Anchor program that creates an SPL token mint with 0 decimals (NFT).",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod nft_mint {
    use super::*;

    pub fn create_nft_mint(ctx: Context<CreateNftMint>) -> Result<()> {
        msg!("NFT mint created: {}", ctx.accounts.mint.key());
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CreateNftMint<'info> {
    #[account(mut)]
    pub creator: Signer<'info>,
    #[account(
        init,
        payer = creator,
        mint::decimals = 0,
        mint::authority = creator,
    )]
    pub mint: Account<'info, Mint>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
}
```

A token with 0 decimals and supply of 1 is the basic NFT pattern on Solana. The mint authority can create exactly 1 token, then the authority should be revoked to make it a true NFT.""")))

EVOL.append(("nft-L1", m(
    "Extend the NFT program to: mint exactly 1 token to the creator, revoke the mint authority after minting, and track the collection.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, MintTo, Token, TokenAccount, SetAuthority};
use anchor_spl::associated_token::AssociatedToken;
use spl_token::instruction::AuthorityType;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod nft_collection {
    use super::*;

    pub fn mint_nft(ctx: Context<MintNft>, name: String) -> Result<()> {
        require!(name.len() <= 32, NftError::NameTooLong);

        // Mint exactly 1 token
        token::mint_to(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), MintTo {
                mint: ctx.accounts.mint.to_account_info(),
                to: ctx.accounts.creator_ata.to_account_info(),
                authority: ctx.accounts.creator.to_account_info(),
            }),
            1,
        )?;

        // Revoke mint authority — no more tokens can be minted
        token::set_authority(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), SetAuthority {
                current_authority: ctx.accounts.creator.to_account_info(),
                account_or_mint: ctx.accounts.mint.to_account_info(),
            }),
            AuthorityType::MintTokens,
            None, // No new authority = permanently revoked
        )?;

        // Track in collection
        let collection = &mut ctx.accounts.collection;
        let nft_record = &mut ctx.accounts.nft_record;
        nft_record.mint = ctx.accounts.mint.key();
        nft_record.creator = ctx.accounts.creator.key();
        nft_record.name = name.clone();
        nft_record.index = collection.current_supply;
        nft_record.bump = ctx.bumps.nft_record;

        collection.current_supply = collection.current_supply
            .checked_add(1).ok_or(NftError::MathOverflow)?;

        emit!(NftMintedEvent {
            mint: ctx.accounts.mint.key(),
            creator: ctx.accounts.creator.key(),
            name,
            index: nft_record.index,
        });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct MintNft<'info> {
    #[account(mut)]
    pub creator: Signer<'info>,
    #[account(
        init,
        payer = creator,
        mint::decimals = 0,
        mint::authority = creator,
    )]
    pub mint: Account<'info, Mint>,
    #[account(
        init,
        payer = creator,
        associated_token::mint = mint,
        associated_token::authority = creator,
    )]
    pub creator_ata: Account<'info, TokenAccount>,
    #[account(
        mut,
        seeds = [b"collection"],
        bump = collection.bump,
        constraint = collection.current_supply < collection.max_supply @ NftError::SoldOut,
    )]
    pub collection: Account<'info, Collection>,
    #[account(
        init,
        payer = creator,
        space = 8 + NftRecord::INIT_SPACE,
        seeds = [b"nft", mint.key().as_ref()],
        bump,
    )]
    pub nft_record: Account<'info, NftRecord>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
}

#[account]
#[derive(InitSpace)]
pub struct Collection {
    pub authority: Pubkey,
    pub max_supply: u32,
    pub current_supply: u32,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct NftRecord {
    pub mint: Pubkey,
    pub creator: Pubkey,
    #[max_len(32)]
    pub name: String,
    pub index: u32,
    pub bump: u8,
}

#[event]
pub struct NftMintedEvent { pub mint: Pubkey, pub creator: Pubkey, pub name: String, pub index: u32 }

#[error_code]
pub enum NftError {
    #[msg("Collection sold out")] SoldOut,
    #[msg("Name too long")] NameTooLong,
    #[msg("Math overflow")] MathOverflow,
}
```""")))

EVOL.append(("nft-L2", m(
    "Add an NFT marketplace to the collection: list for sale, buy, cancel listing, royalty enforcement, and configurable platform fees.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Transfer, Token, TokenAccount};
use anchor_spl::associated_token::AssociatedToken;

declare_id!("11111111111111111111111111111111");

const PLATFORM_FEE_BPS: u16 = 250; // 2.5%

#[program]
pub mod nft_marketplace {
    use super::*;

    pub fn list_nft(ctx: Context<ListNft>, price: u64) -> Result<()> {
        require!(price > 0, MarketError::InvalidPrice);

        // Transfer NFT to escrow
        token::transfer(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), Transfer {
                from: ctx.accounts.seller_ata.to_account_info(),
                to: ctx.accounts.escrow_ata.to_account_info(),
                authority: ctx.accounts.seller.to_account_info(),
            }),
            1,
        )?;

        let listing = &mut ctx.accounts.listing;
        listing.seller = ctx.accounts.seller.key();
        listing.mint = ctx.accounts.mint.key();
        listing.price = price;
        listing.creator = ctx.accounts.nft_record.creator;
        listing.royalty_bps = ctx.accounts.collection.royalty_bps;
        listing.is_active = true;
        listing.bump = ctx.bumps.listing;

        emit!(ListingCreated {
            listing: ctx.accounts.listing.key(),
            seller: listing.seller,
            mint: listing.mint,
            price,
        });
        Ok(())
    }

    pub fn buy_nft(ctx: Context<BuyNft>) -> Result<()> {
        let listing = &ctx.accounts.listing;
        require!(listing.is_active, MarketError::NotActive);
        require!(
            ctx.accounts.buyer.key() != listing.seller,
            MarketError::SellerCannotBuy
        );

        let price = listing.price;

        // Calculate fees
        let platform_fee = (price as u128)
            .checked_mul(PLATFORM_FEE_BPS as u128).ok_or(MarketError::MathOverflow)?
            .checked_div(10_000).ok_or(MarketError::MathOverflow)? as u64;
        let royalty = (price as u128)
            .checked_mul(listing.royalty_bps as u128).ok_or(MarketError::MathOverflow)?
            .checked_div(10_000).ok_or(MarketError::MathOverflow)? as u64;
        let seller_proceeds = price
            .checked_sub(platform_fee).ok_or(MarketError::MathOverflow)?
            .checked_sub(royalty).ok_or(MarketError::MathOverflow)?;

        // Pay seller
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.buyer.key(), &listing.seller, seller_proceeds);
        anchor_lang::solana_program::program::invoke(&ix, &[
            ctx.accounts.buyer.to_account_info(),
            ctx.accounts.seller_account.to_account_info(),
        ])?;

        // Pay platform fee
        if platform_fee > 0 {
            let ix = anchor_lang::solana_program::system_instruction::transfer(
                &ctx.accounts.buyer.key(), &ctx.accounts.treasury.key(), platform_fee);
            anchor_lang::solana_program::program::invoke(&ix, &[
                ctx.accounts.buyer.to_account_info(),
                ctx.accounts.treasury.to_account_info(),
            ])?;
        }

        // Pay royalty to creator
        if royalty > 0 {
            let ix = anchor_lang::solana_program::system_instruction::transfer(
                &ctx.accounts.buyer.key(), &listing.creator, royalty);
            anchor_lang::solana_program::program::invoke(&ix, &[
                ctx.accounts.buyer.to_account_info(),
                ctx.accounts.creator_account.to_account_info(),
            ])?;
        }

        // Transfer NFT from escrow to buyer (PDA-signed)
        let mint_key = listing.mint;
        let seeds = &[b"listing".as_ref(), mint_key.as_ref(), &[listing.bump]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.escrow_ata.to_account_info(),
                    to: ctx.accounts.buyer_ata.to_account_info(),
                    authority: ctx.accounts.listing.to_account_info(),
                },
                &[seeds],
            ),
            1,
        )?;

        let listing = &mut ctx.accounts.listing;
        listing.is_active = false;

        emit!(NftSold {
            mint: mint_key,
            buyer: ctx.accounts.buyer.key(),
            seller: listing.seller,
            price,
            royalty,
            platform_fee,
        });
        Ok(())
    }

    pub fn cancel_listing(ctx: Context<CancelListing>) -> Result<()> {
        let listing = &ctx.accounts.listing;
        require!(listing.is_active, MarketError::NotActive);

        let mint_key = listing.mint;
        let seeds = &[b"listing".as_ref(), mint_key.as_ref(), &[listing.bump]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.escrow_ata.to_account_info(),
                    to: ctx.accounts.seller_ata.to_account_info(),
                    authority: ctx.accounts.listing.to_account_info(),
                },
                &[seeds],
            ),
            1,
        )?;

        let listing = &mut ctx.accounts.listing;
        listing.is_active = false;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Listing {
    pub seller: Pubkey,
    pub mint: Pubkey,
    pub creator: Pubkey,
    pub price: u64,
    pub royalty_bps: u16,
    pub is_active: bool,
    pub bump: u8,
}

#[event] pub struct ListingCreated { pub listing: Pubkey, pub seller: Pubkey, pub mint: Pubkey, pub price: u64 }
#[event] pub struct NftSold { pub mint: Pubkey, pub buyer: Pubkey, pub seller: Pubkey, pub price: u64, pub royalty: u64, pub platform_fee: u64 }

#[error_code]
pub enum MarketError {
    #[msg("Invalid price")] InvalidPrice,
    #[msg("Listing not active")] NotActive,
    #[msg("Seller cannot buy own listing")] SellerCannotBuy,
    #[msg("Math overflow")] MathOverflow,
}
```""")))


# ── Chain 3: Governance / DAO ──────────────────────────────────────────────

EVOL.append(("dao-L0", m(
    "Write a basic Anchor program for creating a proposal with a title and description.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod governance {
    use super::*;

    pub fn create_proposal(
        ctx: Context<CreateProposal>,
        title: String,
        description: String,
    ) -> Result<()> {
        require!(title.len() <= 64, GovError::TitleTooLong);
        require!(description.len() <= 256, GovError::DescriptionTooLong);

        let proposal = &mut ctx.accounts.proposal;
        proposal.proposer = ctx.accounts.proposer.key();
        proposal.title = title;
        proposal.description = description;
        proposal.created_at = Clock::get()?.unix_timestamp;
        proposal.bump = ctx.bumps.proposal;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CreateProposal<'info> {
    #[account(mut)]
    pub proposer: Signer<'info>,
    #[account(
        init,
        payer = proposer,
        space = 8 + Proposal::INIT_SPACE,
        seeds = [b"proposal", proposer.key().as_ref(), &Clock::get()?.unix_timestamp.to_le_bytes()],
        bump,
    )]
    pub proposal: Account<'info, Proposal>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct Proposal {
    pub proposer: Pubkey,
    #[max_len(64)]
    pub title: String,
    #[max_len(256)]
    pub description: String,
    pub created_at: i64,
    pub bump: u8,
}

#[error_code]
pub enum GovError {
    #[msg("Title too long")] TitleTooLong,
    #[msg("Description too long")] DescriptionTooLong,
}
```""")))

EVOL.append(("dao-L1", m(
    "Add voting to the governance program: yes/no votes with a voting period, one vote per wallet, and vote counting.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod governance {
    use super::*;

    pub fn create_proposal(
        ctx: Context<CreateProposal>,
        title: String,
        description: String,
        voting_period: i64,
    ) -> Result<()> {
        require!(title.len() <= 64, GovError::TitleTooLong);
        require!(voting_period > 0, GovError::InvalidPeriod);

        let clock = Clock::get()?;
        let proposal = &mut ctx.accounts.proposal;
        proposal.proposer = ctx.accounts.proposer.key();
        proposal.title = title;
        proposal.description = description;
        proposal.votes_for = 0;
        proposal.votes_against = 0;
        proposal.created_at = clock.unix_timestamp;
        proposal.voting_end = clock.unix_timestamp
            .checked_add(voting_period).ok_or(GovError::MathOverflow)?;
        proposal.is_executed = false;
        proposal.proposal_id = ctx.accounts.dao_config.proposal_count;
        proposal.bump = ctx.bumps.proposal;

        ctx.accounts.dao_config.proposal_count = ctx.accounts.dao_config.proposal_count
            .checked_add(1).ok_or(GovError::MathOverflow)?;
        Ok(())
    }

    pub fn cast_vote(ctx: Context<CastVote>, in_favor: bool) -> Result<()> {
        let proposal = &mut ctx.accounts.proposal;
        let clock = Clock::get()?;

        require!(clock.unix_timestamp <= proposal.voting_end, GovError::VotingEnded);
        require!(!proposal.is_executed, GovError::AlreadyExecuted);

        let vote_record = &mut ctx.accounts.vote_record;
        vote_record.voter = ctx.accounts.voter.key();
        vote_record.proposal = ctx.accounts.proposal.key();
        vote_record.in_favor = in_favor;
        vote_record.voted_at = clock.unix_timestamp;
        vote_record.bump = ctx.bumps.vote_record;

        if in_favor {
            proposal.votes_for = proposal.votes_for
                .checked_add(1).ok_or(GovError::MathOverflow)?;
        } else {
            proposal.votes_against = proposal.votes_against
                .checked_add(1).ok_or(GovError::MathOverflow)?;
        }

        emit!(VoteEvent {
            voter: ctx.accounts.voter.key(),
            proposal: ctx.accounts.proposal.key(),
            in_favor,
        });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CastVote<'info> {
    #[account(mut)]
    pub voter: Signer<'info>,
    #[account(mut)]
    pub proposal: Account<'info, Proposal>,
    #[account(
        init,
        payer = voter,
        space = 8 + VoteRecord::INIT_SPACE,
        seeds = [b"vote", proposal.key().as_ref(), voter.key().as_ref()],
        bump,
    )]
    pub vote_record: Account<'info, VoteRecord>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct Proposal {
    pub proposer: Pubkey,
    #[max_len(64)]
    pub title: String,
    #[max_len(256)]
    pub description: String,
    pub votes_for: u64,
    pub votes_against: u64,
    pub created_at: i64,
    pub voting_end: i64,
    pub is_executed: bool,
    pub proposal_id: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct VoteRecord {
    pub voter: Pubkey,
    pub proposal: Pubkey,
    pub in_favor: bool,
    pub voted_at: i64,
    pub bump: u8,
}

#[event]
pub struct VoteEvent { pub voter: Pubkey, pub proposal: Pubkey, pub in_favor: bool }
```

The `vote_record` PDA with seeds `[b"vote", proposal, voter]` ensures one vote per wallet per proposal — trying to vote again will fail because the PDA already exists.""")))

EVOL.append(("dao-L2", m(
    "Make the governance program token-weighted: votes are weighted by token holdings, add quorum requirements, proposal execution with timelock, and treasury management.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{Token, TokenAccount, Mint};

declare_id!("11111111111111111111111111111111");

#[program]
pub mod token_governance {
    use super::*;

    pub fn create_proposal(
        ctx: Context<CreateProposal>,
        title: String,
        description: String,
    ) -> Result<()> {
        let config = &ctx.accounts.dao_config;
        let voter_tokens = ctx.accounts.proposer_tokens.amount;
        require!(voter_tokens >= config.min_tokens_to_propose, GovError::InsufficientTokens);

        let clock = Clock::get()?;
        let proposal = &mut ctx.accounts.proposal;
        proposal.proposer = ctx.accounts.proposer.key();
        proposal.title = title;
        proposal.description = description;
        proposal.votes_for = 0;
        proposal.votes_against = 0;
        proposal.total_vote_weight = 0;
        proposal.voting_end = clock.unix_timestamp
            .checked_add(config.voting_period).ok_or(GovError::MathOverflow)?;
        proposal.execution_time = clock.unix_timestamp
            .checked_add(config.voting_period).ok_or(GovError::MathOverflow)?
            .checked_add(config.timelock_delay).ok_or(GovError::MathOverflow)?;
        proposal.is_executed = false;
        proposal.bump = ctx.bumps.proposal;
        Ok(())
    }

    pub fn cast_vote(ctx: Context<CastVote>, in_favor: bool) -> Result<()> {
        let clock = Clock::get()?;
        let proposal = &mut ctx.accounts.proposal;
        require!(clock.unix_timestamp <= proposal.voting_end, GovError::VotingEnded);

        // Vote weight = token balance at time of voting
        let weight = ctx.accounts.voter_tokens.amount;
        require!(weight > 0, GovError::NoTokens);

        let vote = &mut ctx.accounts.vote_record;
        vote.voter = ctx.accounts.voter.key();
        vote.weight = weight;
        vote.in_favor = in_favor;
        vote.bump = ctx.bumps.vote_record;

        if in_favor {
            proposal.votes_for = proposal.votes_for
                .checked_add(weight).ok_or(GovError::MathOverflow)?;
        } else {
            proposal.votes_against = proposal.votes_against
                .checked_add(weight).ok_or(GovError::MathOverflow)?;
        }
        proposal.total_vote_weight = proposal.total_vote_weight
            .checked_add(weight).ok_or(GovError::MathOverflow)?;

        emit!(WeightedVote {
            voter: ctx.accounts.voter.key(),
            weight,
            in_favor,
            total_for: proposal.votes_for,
            total_against: proposal.votes_against,
        });
        Ok(())
    }

    pub fn execute_proposal(ctx: Context<ExecuteProposal>) -> Result<()> {
        let proposal = &ctx.accounts.proposal;
        let config = &ctx.accounts.dao_config;
        let clock = Clock::get()?;

        require!(!proposal.is_executed, GovError::AlreadyExecuted);
        require!(clock.unix_timestamp >= proposal.execution_time, GovError::TimelockActive);

        // Check quorum: total votes >= quorum % of total token supply
        let quorum_required = (ctx.accounts.governance_mint.supply as u128)
            .checked_mul(config.quorum_bps as u128).ok_or(GovError::MathOverflow)?
            .checked_div(10_000).ok_or(GovError::MathOverflow)? as u64;
        require!(proposal.total_vote_weight >= quorum_required, GovError::QuorumNotMet);

        // Check majority
        require!(proposal.votes_for > proposal.votes_against, GovError::ProposalRejected);

        let proposal = &mut ctx.accounts.proposal;
        proposal.is_executed = true;

        emit!(ProposalExecuted { proposal: ctx.accounts.proposal.key() });
        Ok(())
    }

    pub fn treasury_transfer(
        ctx: Context<TreasuryTransfer>,
        amount: u64,
    ) -> Result<()> {
        // Only callable after a successful proposal execution
        let proposal = &ctx.accounts.proposal;
        require!(proposal.is_executed, GovError::NotExecuted);

        // Transfer SOL from treasury PDA
        let treasury = &ctx.accounts.treasury;
        **treasury.to_account_info().try_borrow_mut_lamports()? -= amount;
        **ctx.accounts.recipient.to_account_info().try_borrow_mut_lamports()? += amount;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct DaoConfig {
    pub governance_mint: Pubkey,
    pub admin: Pubkey,
    pub voting_period: i64,
    pub timelock_delay: i64,
    pub quorum_bps: u16,        // e.g., 400 = 4% of total supply
    pub min_tokens_to_propose: u64,
    pub proposal_count: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Proposal {
    pub proposer: Pubkey,
    #[max_len(64)]
    pub title: String,
    #[max_len(256)]
    pub description: String,
    pub votes_for: u64,
    pub votes_against: u64,
    pub total_vote_weight: u64,
    pub voting_end: i64,
    pub execution_time: i64,
    pub is_executed: bool,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct VoteRecord {
    pub voter: Pubkey,
    pub weight: u64,
    pub in_favor: bool,
    pub bump: u8,
}

#[event] pub struct WeightedVote { pub voter: Pubkey, pub weight: u64, pub in_favor: bool, pub total_for: u64, pub total_against: u64 }
#[event] pub struct ProposalExecuted { pub proposal: Pubkey }

#[error_code]
pub enum GovError {
    #[msg("Title too long")] TitleTooLong,
    #[msg("Invalid period")] InvalidPeriod,
    #[msg("Insufficient tokens to propose")] InsufficientTokens,
    #[msg("No governance tokens")] NoTokens,
    #[msg("Voting period ended")] VotingEnded,
    #[msg("Already executed")] AlreadyExecuted,
    #[msg("Timelock still active")] TimelockActive,
    #[msg("Quorum not met")] QuorumNotMet,
    #[msg("Proposal rejected by majority")] ProposalRejected,
    #[msg("Proposal not yet executed")] NotExecuted,
    #[msg("Math overflow")] MathOverflow,
}
```""")))


# ── Chain 4: Payment Splitting ──────────────────────────────────────────────

EVOL.append(("payment-L0", m(
    "Write an Anchor program that splits an incoming SOL payment equally between two recipients.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod payment_splitter {
    use super::*;

    pub fn split_payment(ctx: Context<SplitPayment>, amount: u64) -> Result<()> {
        let half = amount.checked_div(2).ok_or(SplitError::MathOverflow)?;
        let remainder = amount.checked_sub(half.checked_mul(2).ok_or(SplitError::MathOverflow)?)
            .ok_or(SplitError::MathOverflow)?;

        // Transfer to recipient 1
        let ix1 = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.payer.key(),
            &ctx.accounts.recipient1.key(),
            half.checked_add(remainder).ok_or(SplitError::MathOverflow)?,
        );
        anchor_lang::solana_program::program::invoke(&ix1, &[
            ctx.accounts.payer.to_account_info(),
            ctx.accounts.recipient1.to_account_info(),
        ])?;

        // Transfer to recipient 2
        let ix2 = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.payer.key(),
            &ctx.accounts.recipient2.key(),
            half,
        );
        anchor_lang::solana_program::program::invoke(&ix2, &[
            ctx.accounts.payer.to_account_info(),
            ctx.accounts.recipient2.to_account_info(),
        ])?;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct SplitPayment<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,
    /// CHECK: recipient 1
    #[account(mut)]
    pub recipient1: UncheckedAccount<'info>,
    /// CHECK: recipient 2
    #[account(mut)]
    pub recipient2: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}

#[error_code]
pub enum SplitError {
    #[msg("Math overflow")] MathOverflow,
}
```""")))

EVOL.append(("payment-L1", m(
    "Extend the payment splitter to support N recipients with configurable percentage shares (basis points).",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

const MAX_RECIPIENTS: usize = 10;

#[program]
pub mod payment_splitter {
    use super::*;

    pub fn initialize(
        ctx: Context<Initialize>,
        recipients: Vec<Pubkey>,
        shares_bps: Vec<u16>,
    ) -> Result<()> {
        require!(recipients.len() == shares_bps.len(), SplitError::MismatchedLengths);
        require!(recipients.len() <= MAX_RECIPIENTS, SplitError::TooManyRecipients);
        require!(!recipients.is_empty(), SplitError::NoRecipients);

        let total_bps: u32 = shares_bps.iter().map(|&s| s as u32).sum();
        require!(total_bps == 10_000, SplitError::SharesNotComplete);

        let config = &mut ctx.accounts.config;
        config.admin = ctx.accounts.admin.key();
        config.recipient_count = recipients.len() as u8;
        for (i, (recipient, share)) in recipients.iter().zip(shares_bps.iter()).enumerate() {
            config.recipients[i] = *recipient;
            config.shares_bps[i] = *share;
        }
        config.bump = ctx.bumps.config;
        Ok(())
    }

    pub fn distribute(ctx: Context<Distribute>, total_amount: u64) -> Result<()> {
        let config = &ctx.accounts.config;

        let mut distributed: u64 = 0;
        for (i, account_info) in ctx.remaining_accounts.iter().enumerate() {
            if i >= config.recipient_count as usize { break; }
            require!(
                account_info.key() == config.recipients[i],
                SplitError::WrongRecipient
            );

            let share = if i == (config.recipient_count as usize - 1) {
                // Last recipient gets remainder to handle rounding
                total_amount.checked_sub(distributed).ok_or(SplitError::MathOverflow)?
            } else {
                (total_amount as u128)
                    .checked_mul(config.shares_bps[i] as u128).ok_or(SplitError::MathOverflow)?
                    .checked_div(10_000).ok_or(SplitError::MathOverflow)? as u64
            };

            let ix = anchor_lang::solana_program::system_instruction::transfer(
                &ctx.accounts.payer.key(), account_info.key, share);
            anchor_lang::solana_program::program::invoke(&ix, &[
                ctx.accounts.payer.to_account_info(),
                account_info.clone(),
            ])?;
            distributed = distributed.checked_add(share).ok_or(SplitError::MathOverflow)?;
        }

        emit!(PaymentDistributed { total: total_amount, recipients: config.recipient_count });
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct SplitConfig {
    pub admin: Pubkey,
    pub recipients: [Pubkey; 10],
    pub shares_bps: [u16; 10],
    pub recipient_count: u8,
    pub bump: u8,
}

#[event]
pub struct PaymentDistributed { pub total: u64, pub recipients: u8 }

#[error_code]
pub enum SplitError {
    #[msg("Recipients and shares length mismatch")] MismatchedLengths,
    #[msg("Too many recipients (max 10)")] TooManyRecipients,
    #[msg("No recipients")] NoRecipients,
    #[msg("Shares must sum to 10000 bps")] SharesNotComplete,
    #[msg("Wrong recipient")] WrongRecipient,
    #[msg("Math overflow")] MathOverflow,
}
```""")))


# ── Chain 5: Lottery / Raffle ──────────────────────────────────────────────

EVOL.append(("lottery-L0", m(
    "Write a basic Anchor program where users buy lottery tickets by depositing SOL.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

const TICKET_PRICE: u64 = 100_000_000; // 0.1 SOL

#[program]
pub mod lottery {
    use super::*;

    pub fn buy_ticket(ctx: Context<BuyTicket>) -> Result<()> {
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.buyer.key(),
            &ctx.accounts.pool.key(),
            TICKET_PRICE,
        );
        anchor_lang::solana_program::program::invoke(&ix, &[
            ctx.accounts.buyer.to_account_info(),
            ctx.accounts.pool.to_account_info(),
        ])?;

        let ticket = &mut ctx.accounts.ticket;
        ticket.owner = ctx.accounts.buyer.key();
        ticket.ticket_number = ctx.accounts.lottery_state.ticket_count;
        ticket.bump = ctx.bumps.ticket;

        let state = &mut ctx.accounts.lottery_state;
        state.ticket_count = state.ticket_count.checked_add(1).ok_or(LotteryError::MathOverflow)?;
        state.prize_pool = state.prize_pool
            .checked_add(TICKET_PRICE).ok_or(LotteryError::MathOverflow)?;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct BuyTicket<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,
    /// CHECK: prize pool PDA
    #[account(mut, seeds = [b"pool"], bump)]
    pub pool: SystemAccount<'info>,
    #[account(mut, seeds = [b"lottery"], bump = lottery_state.bump)]
    pub lottery_state: Account<'info, LotteryState>,
    #[account(
        init, payer = buyer,
        space = 8 + Ticket::INIT_SPACE,
        seeds = [b"ticket", &lottery_state.ticket_count.to_le_bytes()],
        bump,
    )]
    pub ticket: Account<'info, Ticket>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct LotteryState {
    pub authority: Pubkey,
    pub ticket_count: u64,
    pub prize_pool: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Ticket {
    pub owner: Pubkey,
    pub ticket_number: u64,
    pub bump: u8,
}

#[error_code]
pub enum LotteryError {
    #[msg("Math overflow")] MathOverflow,
}
```""")))

EVOL.append(("lottery-L1", m(
    "Add a winner selection mechanism using a pseudo-random slot hash, a draw deadline, and prize claiming.",
    """```rust
use anchor_lang::prelude::*;
use anchor_lang::solana_program::sysvar::slot_hashes;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod lottery {
    use super::*;

    pub fn draw_winner(ctx: Context<DrawWinner>) -> Result<()> {
        let state = &mut ctx.accounts.lottery_state;
        let clock = Clock::get()?;

        require!(clock.unix_timestamp >= state.draw_time, LotteryError::TooEarly);
        require!(!state.is_drawn, LotteryError::AlreadyDrawn);
        require!(state.ticket_count > 0, LotteryError::NoTickets);

        // Use recent slot hash for randomness (acceptable for low-stakes)
        let slot_hashes_info = &ctx.accounts.slot_hashes;
        let data = slot_hashes_info.try_borrow_data()?;
        // Take first 8 bytes of slot hash data as seed
        let seed = u64::from_le_bytes(data[16..24].try_into().unwrap());
        let winning_number = seed % state.ticket_count;

        state.winning_ticket = winning_number;
        state.is_drawn = true;

        emit!(WinnerDrawn { winning_ticket: winning_number, total_tickets: state.ticket_count });
        Ok(())
    }

    pub fn claim_prize(ctx: Context<ClaimPrize>) -> Result<()> {
        let state = &ctx.accounts.lottery_state;
        require!(state.is_drawn, LotteryError::NotDrawn);
        require!(
            ctx.accounts.ticket.ticket_number == state.winning_ticket,
            LotteryError::NotWinner
        );
        require!(!state.is_claimed, LotteryError::AlreadyClaimed);

        let pool = &ctx.accounts.pool;
        let prize = state.prize_pool;

        **pool.to_account_info().try_borrow_mut_lamports()? -= prize;
        **ctx.accounts.winner.to_account_info().try_borrow_mut_lamports()? += prize;

        let state = &mut ctx.accounts.lottery_state;
        state.is_claimed = true;

        emit!(PrizeClaimed { winner: ctx.accounts.winner.key(), amount: prize });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct DrawWinner<'info> {
    pub authority: Signer<'info>,
    #[account(mut, seeds = [b"lottery"], bump = lottery_state.bump, has_one = authority)]
    pub lottery_state: Account<'info, LotteryState>,
    /// CHECK: SlotHashes sysvar
    #[account(address = slot_hashes::id())]
    pub slot_hashes: UncheckedAccount<'info>,
}

#[account]
#[derive(InitSpace)]
pub struct LotteryState {
    pub authority: Pubkey,
    pub ticket_count: u64,
    pub prize_pool: u64,
    pub draw_time: i64,
    pub winning_ticket: u64,
    pub is_drawn: bool,
    pub is_claimed: bool,
    pub bump: u8,
}

#[error_code]
pub enum LotteryError {
    #[msg("Too early to draw")] TooEarly,
    #[msg("Winner already drawn")] AlreadyDrawn,
    #[msg("No tickets sold")] NoTickets,
    #[msg("Winner not drawn yet")] NotDrawn,
    #[msg("Not the winning ticket")] NotWinner,
    #[msg("Prize already claimed")] AlreadyClaimed,
    #[msg("Math overflow")] MathOverflow,
}
```

**Warning:** Slot hashes are manipulable by validators. For production lotteries, use Switchboard VRF or another verifiable randomness source.""")))


# ═══════════════════════════════════════════════════════════════════════════════
# DPO: Preference pairs (chosen vs rejected) for alignment training
# Based on Asymmetric Research misinformation + common mistakes
# ═══════════════════════════════════════════════════════════════════════════════

DPO_PAIRS = [
    # Reentrancy misconception
    ("Does Solana have reentrancy attacks like Ethereum?",
     # CHOSEN (correct)
     """No, Solana does NOT have Ethereum-style reentrancy attacks. The Solana runtime prevents this architecturally:

1. **CPI depth limit**: Maximum 4 levels of cross-program invocation
2. **Account locking**: When a program modifies an account, it's locked — no other program can modify it simultaneously in the same CPI chain
3. **Single-threaded execution per transaction**: Instructions execute sequentially within a transaction

You do NOT need reentrancy guards on Solana. Adding them is unnecessary complexity:

```rust
// ❌ UNNECESSARY on Solana — this is an Ethereum pattern
pub has_entered: bool, // reentrancy guard flag

// ✅ CORRECT — just validate inputs and check balances
pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
    let vault = &mut ctx.accounts.vault;
    require!(vault.balance >= amount, MyError::InsufficientFunds);
    vault.balance -= amount;
    // Transfer SOL...
    Ok(())
}
```

Focus on real Solana security concerns instead: signer verification, account ownership checks, and arithmetic overflow.""",
     # REJECTED (incorrect — suggests reentrancy is a risk)
     """Yes, reentrancy is a concern on Solana. You should add a reentrancy guard to protect your programs:

```rust
#[account]
pub struct Vault {
    pub balance: u64,
    pub is_locked: bool, // reentrancy guard
}

pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
    let vault = &mut ctx.accounts.vault;
    require!(!vault.is_locked, MyError::ReentrancyDetected);
    vault.is_locked = true;
    // ... transfer ...
    vault.is_locked = false;
    Ok(())
}
```

Always use the checks-effects-interactions pattern and add reentrancy guards to any function that sends SOL or tokens."""),

    # Closed account discriminator — fixed in Anchor
    ("Do I need to worry about closed account discriminator attacks in Anchor?",
     # CHOSEN
     """No, this is a **solved issue** in modern Anchor (0.25.0+). When you use the `close` constraint, Anchor:

1. Transfers all lamports out
2. Zeros the account data (including the 8-byte discriminator)
3. Assigns the account to the system program

```rust
// Safe — Anchor handles everything
#[account(
    mut,
    close = receiver,
    has_one = authority,
)]
pub my_account: Account<'info, MyData>,
```

When any instruction later tries to use this address, Anchor's deserialization will fail because:
- The account is now owned by the system program (not your program)
- The discriminator is zeroed out

You do NOT need to manually set a "closed" flag or check for it. This vulnerability was fixed years ago. Focus on real security patterns like proper signer verification and authorization checks.""",
     # REJECTED
     """Yes, the closed account discriminator attack is a serious vulnerability. When you close an account, someone could re-create it at the same address and trick your program into treating it as a valid account.

You should add a manual check:
```rust
#[account]
pub struct MyData {
    pub is_closed: bool, // Must check this manually!
    // ... other fields
}

pub fn close_account(ctx: Context<CloseAccount>) -> Result<()> {
    let account = &mut ctx.accounts.my_data;
    account.is_closed = true; // Mark as closed
    // ... transfer lamports ...
    Ok(())
}
```

Always check `is_closed` before operating on any account."""),

    # Float determinism on Solana
    ("Are floating point operations non-deterministic on Solana?",
     # CHOSEN
     """No, floating point operations ARE deterministic on Solana. The SBF/BPF target uses LLVM's software floating-point emulation, which produces identical results across all validators regardless of hardware.

However, you should still avoid floats in Solana programs for a different reason: **precision loss**. Use fixed-point arithmetic instead:

```rust
// ❌ Technically works but loses precision
let fee = amount as f64 * 0.025;

// ✅ Better: fixed-point with basis points
let fee = (amount as u128)
    .checked_mul(250) // 2.5% = 250 bps
    .ok_or(MyError::Overflow)?
    .checked_div(10_000)
    .ok_or(MyError::Overflow)? as u64;

// ✅ Better: scaled integers for prices
// Store price as u64 with 6 decimal precision
let price_scaled = 1_500_000; // represents $1.50
let value = (amount as u128)
    .checked_mul(price_scaled as u128)
    .ok_or(MyError::Overflow)?
    .checked_div(1_000_000)
    .ok_or(MyError::Overflow)? as u64;
```

The reason to avoid floats is precision loss and rounding errors, NOT non-determinism.""",
     # REJECTED
     """Floating point operations are non-deterministic on Solana because different validators may use different CPU architectures (x86, ARM) that implement IEEE 754 slightly differently.

Never use f32 or f64 in your Solana programs — validators will disagree on the result and your transaction will fail or produce inconsistent state.

Always use integer math:
```rust
// Use integers only!
let fee = amount * 25 / 1000;
```"""),

    # Deprecated API patterns
    ("Should I use `load_instruction_at` in my Solana program?",
     # CHOSEN
     """No, `load_instruction_at` is **deprecated**. Use `get_instruction_relative` or `load_instruction_at_checked` instead:

```rust
use anchor_lang::solana_program::sysvar::instructions::{
    self,
    get_instruction_relative,
    load_instruction_at_checked,
};

// ✅ CORRECT: Use get_instruction_relative
pub fn verify_ed25519(ctx: Context<Verify>) -> Result<()> {
    let ix_sysvar = &ctx.accounts.instruction_sysvar;

    // Get the previous instruction (Ed25519 verify)
    let prev_ix = get_instruction_relative(-1, ix_sysvar)?;

    require!(
        prev_ix.program_id == anchor_lang::solana_program::ed25519_program::id(),
        MyError::InvalidInstruction
    );
    Ok(())
}

#[derive(Accounts)]
pub struct Verify<'info> {
    /// CHECK: Instructions sysvar
    #[account(address = instructions::id())]
    pub instruction_sysvar: UncheckedAccount<'info>,
}
```

`get_instruction_relative` is safer because it uses relative indexing (no off-by-one errors) and is the current recommended API.""",
     # REJECTED
     """Use `load_instruction_at` to access other instructions in the transaction:

```rust
use solana_program::sysvar::instructions::load_instruction_at;

let ix = load_instruction_at(0, &ctx.accounts.instruction_sysvar)?;
```

This function loads the instruction at the given absolute index."""),

    # Anchor version patterns
    ("Should I use `declare_id!` or `declare_program!` in Anchor?",
     # CHOSEN
     """Use `declare_id!` — it's the standard way to declare your program ID in Anchor:

```rust
use anchor_lang::prelude::*;

// ✅ Standard program ID declaration
declare_id!("YourProgramId11111111111111111111111111111");

#[program]
pub mod my_program {
    use super::*;
    // ...
}
```

`declare_program!` is used for a different purpose — it's for generating CPI client code to call OTHER programs:

```rust
// Used to generate a CPI interface for calling another program
declare_program!(other_program, "OtherProgramId...");

// Then in your instruction:
pub fn call_other(ctx: Context<CallOther>) -> Result<()> {
    other_program::cpi::some_instruction(ctx.accounts.cpi_ctx())?;
    Ok(())
}
```

Summary:
- `declare_id!` → Your program's ID (every program needs this)
- `declare_program!` → Generate CPI bindings for external programs (Anchor 0.30+)""",
     # REJECTED
     """In Anchor 0.30+, you should use `declare_program!` instead of `declare_id!`:

```rust
// Old way (deprecated)
declare_id!("YourProgramId...");

// New way
declare_program!("YourProgramId...");
```

`declare_program!` is the modern replacement for `declare_id!`."""),

    # coral-xyz vs solana-foundation
    ("Which GitHub org should I use for Anchor — coral-xyz or solana-foundation?",
     # CHOSEN
     """Use **solana-foundation/anchor** — the Anchor repository has been transferred to the Solana Foundation:

```toml
# Cargo.toml — both work, but solana-foundation is canonical
[dependencies]
anchor-lang = "0.30.1"
# The crate is published on crates.io, so the GitHub org doesn't matter
# for dependencies. But for cloning/issues/PRs:
```

```bash
# ✅ Current canonical repo
git clone https://github.com/solana-foundation/anchor

# ⚠️ Old location (redirects, but use the new one)
# git clone https://github.com/coral-xyz/anchor
```

For npm packages, use `@coral-xyz/anchor` — the npm package name hasn't changed:
```json
{
  "dependencies": {
    "@coral-xyz/anchor": "^0.30.1"
  }
}
```

The transfer happened in 2024. Code functionality is identical — it's the same project, just under new stewardship.""",
     # REJECTED
     """Use coral-xyz/anchor — that's the official Anchor repository maintained by the Coral team:

```bash
git clone https://github.com/coral-xyz/anchor
```

The npm package is `@coral-xyz/anchor` and the Rust crate is `anchor-lang` from the coral-xyz organization."""),

    # Security misconception: Solana programs are immutable
    ("Are deployed Solana programs immutable?",
     # CHOSEN
     """By default, Solana programs are **upgradeable**, not immutable. The deployer retains an upgrade authority:

```bash
# Check upgrade authority
solana program show <PROGRAM_ID>

# Upgrade a program
solana program deploy --program-id <PROGRAM_ID> target/deploy/my_program.so

# Make it truly immutable (irreversible!)
solana program set-upgrade-authority <PROGRAM_ID> --final
```

```rust
// In Anchor, set upgrade authority in Anchor.toml:
[programs.mainnet]
my_program = "YOUR_PROGRAM_ID"
```

**Security implications:**
- Upgradeable programs can be changed by the upgrade authority → trust model
- For DeFi protocols, consider: multisig upgrade authority, timelock, or making it immutable
- Users should check `solana program show` to see if a program is upgradeable
- Making a program immutable (`--final`) is permanent and cannot be undone

Programs are stored in separate data accounts and can be upgraded by replacing the data while keeping the same program ID.""",
     # REJECTED
     """Once deployed, Solana programs are immutable — they cannot be changed. This is a key security feature of the blockchain.

If you need to fix a bug, you'll need to deploy a new program with a new program ID and migrate users."""),

    # Misconception: account size
    ("Can I change an account's size after creation on Solana?",
     # CHOSEN
     """Yes! Use `realloc` in Anchor to resize accounts:

```rust
#[derive(Accounts)]
pub struct ResizeAccount<'info> {
    #[account(
        mut,
        realloc = 8 + NewSize::INIT_SPACE,
        realloc::payer = payer,
        realloc::zero = false,
    )]
    pub my_account: Account<'info, MyData>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

Rules:
- Growing: payer provides additional rent lamports
- Shrinking: excess lamports returned to payer
- `realloc::zero = true` zeros new bytes (useful for security)
- Max single realloc: 10KB increase per instruction
- For larger changes, call realloc multiple times across transactions

At the native level, use `AccountInfo::realloc()`:
```rust
account_info.realloc(new_size, false)?;
```""",
     # REJECTED
     """No, account sizes are fixed at creation time on Solana. You must specify the exact size when creating the account and it cannot be changed later.

If you need more space, create a new larger account and migrate the data."""),
]

for question, chosen, rejected in DPO_PAIRS:
    DPO_CHOSEN.append(("dpo", m(question, chosen)))
    DPO_REJECTED.append(("dpo", m(question, rejected)))


# ═══════════════════════════════════════════════════════════════════════════════
# OSS-INSTRUCT: Code seed → complete program
# ═══════════════════════════════════════════════════════════════════════════════

OSS_SEEDS = [
    ("counter with reset",
     "Given this code seed, build a complete Anchor program:\n```rust\npub counter: u64,\npub authority: Pubkey,\npub fn increment() { counter += 1; }\n```",
     """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod counter {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.authority = ctx.accounts.authority.key();
        counter.count = 0;
        counter.bump = ctx.bumps.counter;
        Ok(())
    }

    pub fn increment(ctx: Context<Modify>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.count = counter.count.checked_add(1).ok_or(CounterError::Overflow)?;
        emit!(CountChanged { count: counter.count });
        Ok(())
    }

    pub fn decrement(ctx: Context<Modify>) -> Result<()> {
        let counter = &mut ctx.accounts.counter;
        counter.count = counter.count.checked_sub(1).ok_or(CounterError::Underflow)?;
        emit!(CountChanged { count: counter.count });
        Ok(())
    }

    pub fn reset(ctx: Context<Modify>) -> Result<()> {
        ctx.accounts.counter.count = 0;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        init, payer = authority,
        space = 8 + Counter::INIT_SPACE,
        seeds = [b"counter", authority.key().as_ref()], bump,
    )]
    pub counter: Account<'info, Counter>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Modify<'info> {
    pub authority: Signer<'info>,
    #[account(
        mut,
        seeds = [b"counter", authority.key().as_ref()],
        bump = counter.bump,
        has_one = authority,
    )]
    pub counter: Account<'info, Counter>,
}

#[account]
#[derive(InitSpace)]
pub struct Counter {
    pub authority: Pubkey,
    pub count: u64,
    pub bump: u8,
}

#[event]
pub struct CountChanged { pub count: u64 }

#[error_code]
pub enum CounterError {
    #[msg("Counter overflow")] Overflow,
    #[msg("Counter underflow")] Underflow,
}
```"""),

    ("whitelist",
     "Given this code seed, build a complete Anchor program:\n```rust\npub members: Vec<Pubkey>,\npub fn add_member(member: Pubkey) {}\npub fn is_member(key: Pubkey) -> bool {}\n```",
     """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

const MAX_MEMBERS: usize = 50;

#[program]
pub mod whitelist {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let wl = &mut ctx.accounts.whitelist;
        wl.admin = ctx.accounts.admin.key();
        wl.member_count = 0;
        wl.bump = ctx.bumps.whitelist;
        Ok(())
    }

    pub fn add_member(ctx: Context<AdminAction>, member: Pubkey) -> Result<()> {
        let wl = &mut ctx.accounts.whitelist;
        require!((wl.member_count as usize) < MAX_MEMBERS, WlError::Full);

        // Check not already a member
        for i in 0..wl.member_count as usize {
            require!(wl.members[i] != member, WlError::AlreadyMember);
        }

        wl.members[wl.member_count as usize] = member;
        wl.member_count += 1;

        emit!(MemberAdded { member, total: wl.member_count });
        Ok(())
    }

    pub fn remove_member(ctx: Context<AdminAction>, member: Pubkey) -> Result<()> {
        let wl = &mut ctx.accounts.whitelist;
        let mut found = false;

        for i in 0..wl.member_count as usize {
            if wl.members[i] == member {
                // Swap with last element and decrease count
                wl.members[i] = wl.members[wl.member_count as usize - 1];
                wl.members[wl.member_count as usize - 1] = Pubkey::default();
                wl.member_count -= 1;
                found = true;
                break;
            }
        }

        require!(found, WlError::NotMember);
        emit!(MemberRemoved { member, total: wl.member_count });
        Ok(())
    }

    pub fn member_action(ctx: Context<MemberAction>) -> Result<()> {
        let wl = &ctx.accounts.whitelist;
        let caller = ctx.accounts.member.key();
        let is_member = wl.members[..wl.member_count as usize]
            .iter()
            .any(|m| *m == caller);
        require!(is_member, WlError::NotMember);
        // ... perform gated action ...
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(init, payer = admin, space = 8 + Whitelist::INIT_SPACE, seeds = [b"whitelist"], bump)]
    pub whitelist: Account<'info, Whitelist>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AdminAction<'info> {
    pub admin: Signer<'info>,
    #[account(mut, seeds = [b"whitelist"], bump = whitelist.bump, has_one = admin)]
    pub whitelist: Account<'info, Whitelist>,
}

#[derive(Accounts)]
pub struct MemberAction<'info> {
    pub member: Signer<'info>,
    #[account(seeds = [b"whitelist"], bump = whitelist.bump)]
    pub whitelist: Account<'info, Whitelist>,
}

#[account]
#[derive(InitSpace)]
pub struct Whitelist {
    pub admin: Pubkey,
    pub members: [Pubkey; 50],
    pub member_count: u8,
    pub bump: u8,
}

#[event] pub struct MemberAdded { pub member: Pubkey, pub total: u8 }
#[event] pub struct MemberRemoved { pub member: Pubkey, pub total: u8 }

#[error_code]
pub enum WlError {
    #[msg("Whitelist full")] Full,
    #[msg("Already a member")] AlreadyMember,
    #[msg("Not a member")] NotMember,
}
```"""),

    ("timelock",
     "Given this code seed, build a complete Anchor program:\n```rust\npub execute_after: i64,\npub fn queue_action() {}\npub fn execute_action() { require!(now >= execute_after) }\n```",
     """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

const MIN_DELAY: i64 = 3600; // 1 hour minimum
const MAX_DELAY: i64 = 604800; // 7 days maximum

#[program]
pub mod timelock {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, delay: i64) -> Result<()> {
        require!(delay >= MIN_DELAY && delay <= MAX_DELAY, TlError::InvalidDelay);
        let config = &mut ctx.accounts.config;
        config.admin = ctx.accounts.admin.key();
        config.delay = delay;
        config.bump = ctx.bumps.config;
        Ok(())
    }

    pub fn queue_action(ctx: Context<QueueAction>, action_id: u64, data_hash: [u8; 32]) -> Result<()> {
        let clock = Clock::get()?;
        let action = &mut ctx.accounts.queued_action;
        action.admin = ctx.accounts.admin.key();
        action.action_id = action_id;
        action.data_hash = data_hash;
        action.queued_at = clock.unix_timestamp;
        action.execute_after = clock.unix_timestamp
            .checked_add(ctx.accounts.config.delay).ok_or(TlError::MathOverflow)?;
        action.is_executed = false;
        action.is_cancelled = false;
        action.bump = ctx.bumps.queued_action;

        emit!(ActionQueued { action_id, execute_after: action.execute_after });
        Ok(())
    }

    pub fn execute_action(ctx: Context<ExecuteAction>) -> Result<()> {
        let action = &mut ctx.accounts.queued_action;
        let clock = Clock::get()?;

        require!(!action.is_executed, TlError::AlreadyExecuted);
        require!(!action.is_cancelled, TlError::Cancelled);
        require!(clock.unix_timestamp >= action.execute_after, TlError::TooEarly);

        action.is_executed = true;
        emit!(ActionExecuted { action_id: action.action_id });
        Ok(())
    }

    pub fn cancel_action(ctx: Context<CancelAction>) -> Result<()> {
        let action = &mut ctx.accounts.queued_action;
        require!(!action.is_executed, TlError::AlreadyExecuted);
        action.is_cancelled = true;
        emit!(ActionCancelled { action_id: action.action_id });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(init, payer = admin, space = 8 + TimelockConfig::INIT_SPACE, seeds = [b"config"], bump)]
    pub config: Account<'info, TimelockConfig>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(action_id: u64)]
pub struct QueueAction<'info> {
    pub admin: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, TimelockConfig>,
    #[account(
        init, payer = admin,
        space = 8 + QueuedAction::INIT_SPACE,
        seeds = [b"action", &action_id.to_le_bytes()], bump,
    )]
    pub queued_action: Account<'info, QueuedAction>,
    #[account(mut)]
    _payer: Signer<'info>, // same as admin
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ExecuteAction<'info> {
    pub admin: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, TimelockConfig>,
    #[account(mut, has_one = admin)]
    pub queued_action: Account<'info, QueuedAction>,
}

#[derive(Accounts)]
pub struct CancelAction<'info> {
    pub admin: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, TimelockConfig>,
    #[account(mut, has_one = admin)]
    pub queued_action: Account<'info, QueuedAction>,
}

#[account]
#[derive(InitSpace)]
pub struct TimelockConfig {
    pub admin: Pubkey,
    pub delay: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct QueuedAction {
    pub admin: Pubkey,
    pub action_id: u64,
    pub data_hash: [u8; 32],
    pub queued_at: i64,
    pub execute_after: i64,
    pub is_executed: bool,
    pub is_cancelled: bool,
    pub bump: u8,
}

#[event] pub struct ActionQueued { pub action_id: u64, pub execute_after: i64 }
#[event] pub struct ActionExecuted { pub action_id: u64 }
#[event] pub struct ActionCancelled { pub action_id: u64 }

#[error_code]
pub enum TlError {
    #[msg("Invalid delay")] InvalidDelay,
    #[msg("Already executed")] AlreadyExecuted,
    #[msg("Action cancelled")] Cancelled,
    #[msg("Timelock not expired")] TooEarly,
    #[msg("Math overflow")] MathOverflow,
}
```"""),

    ("rate limiter",
     "Given this code seed, build a complete Anchor program:\n```rust\npub last_action_time: i64,\npub action_count: u32,\npub fn check_rate_limit() { require!(now - last > cooldown) }\n```",
     """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod rate_limited {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, cooldown_seconds: i64, max_per_window: u32) -> Result<()> {
        let config = &mut ctx.accounts.config;
        config.admin = ctx.accounts.admin.key();
        config.cooldown_seconds = cooldown_seconds;
        config.max_per_window = max_per_window;
        config.window_seconds = 3600; // 1 hour window
        config.bump = ctx.bumps.config;
        Ok(())
    }

    pub fn rate_limited_action(ctx: Context<RateLimitedAction>) -> Result<()> {
        let clock = Clock::get()?;
        let user_limits = &mut ctx.accounts.user_limits;
        let config = &ctx.accounts.config;

        // Check per-action cooldown
        let elapsed = clock.unix_timestamp
            .checked_sub(user_limits.last_action_time).ok_or(RateError::MathOverflow)?;
        require!(elapsed >= config.cooldown_seconds, RateError::CooldownActive);

        // Check window-based rate limit
        let window_elapsed = clock.unix_timestamp
            .checked_sub(user_limits.window_start).ok_or(RateError::MathOverflow)?;
        if window_elapsed >= config.window_seconds {
            // New window
            user_limits.window_start = clock.unix_timestamp;
            user_limits.window_count = 0;
        }
        require!(user_limits.window_count < config.max_per_window, RateError::RateLimitExceeded);

        // Update counters
        user_limits.last_action_time = clock.unix_timestamp;
        user_limits.window_count = user_limits.window_count
            .checked_add(1).ok_or(RateError::MathOverflow)?;
        user_limits.total_actions = user_limits.total_actions
            .checked_add(1).ok_or(RateError::MathOverflow)?;

        // ... perform the actual action ...
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(init, payer = admin, space = 8 + RateLimitConfig::INIT_SPACE, seeds = [b"config"], bump)]
    pub config: Account<'info, RateLimitConfig>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RateLimitedAction<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, RateLimitConfig>,
    #[account(
        init_if_needed, payer = user,
        space = 8 + UserRateLimit::INIT_SPACE,
        seeds = [b"rate-limit", user.key().as_ref()], bump,
    )]
    pub user_limits: Account<'info, UserRateLimit>,
    pub system_program: Program<'info, System>,
}

#[account]
#[derive(InitSpace)]
pub struct RateLimitConfig {
    pub admin: Pubkey,
    pub cooldown_seconds: i64,
    pub max_per_window: u32,
    pub window_seconds: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct UserRateLimit {
    pub user: Pubkey,
    pub last_action_time: i64,
    pub window_start: i64,
    pub window_count: u32,
    pub total_actions: u64,
    pub bump: u8,
}

#[error_code]
pub enum RateError {
    #[msg("Cooldown period still active")] CooldownActive,
    #[msg("Rate limit exceeded")] RateLimitExceeded,
    #[msg("Math overflow")] MathOverflow,
}
```"""),

    ("subscription service",
     "Given this code seed, build a complete Anchor program:\n```rust\npub plan: u8,\npub expires_at: i64,\npub fn subscribe(plan, duration) {}\npub fn is_active() -> bool { now < expires_at }\n```",
     """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod subscriptions {
    use super::*;

    pub fn create_plan(ctx: Context<CreatePlan>, plan_id: u8, price: u64, duration_days: u16) -> Result<()> {
        let plan = &mut ctx.accounts.plan;
        plan.admin = ctx.accounts.admin.key();
        plan.plan_id = plan_id;
        plan.price = price;
        plan.duration_seconds = (duration_days as i64) * 86400;
        plan.is_active = true;
        plan.subscriber_count = 0;
        plan.bump = ctx.bumps.plan;
        Ok(())
    }

    pub fn subscribe(ctx: Context<Subscribe>) -> Result<()> {
        let plan = &ctx.accounts.plan;
        require!(plan.is_active, SubError::PlanInactive);

        let clock = Clock::get()?;
        let sub = &mut ctx.accounts.subscription;

        // If renewing, extend from current expiry (not from now)
        let start = if sub.expires_at > clock.unix_timestamp {
            sub.expires_at
        } else {
            clock.unix_timestamp
        };

        sub.subscriber = ctx.accounts.subscriber.key();
        sub.plan_id = plan.plan_id;
        sub.started_at = if sub.started_at == 0 { clock.unix_timestamp } else { sub.started_at };
        sub.expires_at = start.checked_add(plan.duration_seconds).ok_or(SubError::MathOverflow)?;
        sub.bump = ctx.bumps.subscription;

        // Pay subscription fee
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.subscriber.key(),
            &ctx.accounts.treasury.key(),
            plan.price,
        );
        anchor_lang::solana_program::program::invoke(&ix, &[
            ctx.accounts.subscriber.to_account_info(),
            ctx.accounts.treasury.to_account_info(),
        ])?;

        let plan = &mut ctx.accounts.plan;
        plan.subscriber_count = plan.subscriber_count.checked_add(1).ok_or(SubError::MathOverflow)?;

        emit!(Subscribed {
            subscriber: ctx.accounts.subscriber.key(),
            plan_id: plan.plan_id,
            expires_at: sub.expires_at,
        });
        Ok(())
    }

    pub fn gated_feature(ctx: Context<GatedFeature>) -> Result<()> {
        let clock = Clock::get()?;
        require!(
            ctx.accounts.subscription.expires_at > clock.unix_timestamp,
            SubError::Expired
        );
        // ... premium feature logic ...
        msg!("Premium feature accessed!");
        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(plan_id: u8)]
pub struct CreatePlan<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(init, payer = admin, space = 8 + Plan::INIT_SPACE, seeds = [b"plan", &[plan_id]], bump)]
    pub plan: Account<'info, Plan>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Subscribe<'info> {
    #[account(mut)]
    pub subscriber: Signer<'info>,
    #[account(mut, seeds = [b"plan", &[plan.plan_id]], bump = plan.bump)]
    pub plan: Account<'info, Plan>,
    #[account(
        init_if_needed, payer = subscriber,
        space = 8 + Subscription::INIT_SPACE,
        seeds = [b"sub", subscriber.key().as_ref(), &[plan.plan_id]], bump,
    )]
    pub subscription: Account<'info, Subscription>,
    /// CHECK: treasury PDA
    #[account(mut, seeds = [b"treasury"], bump)]
    pub treasury: SystemAccount<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct GatedFeature<'info> {
    pub subscriber: Signer<'info>,
    #[account(
        seeds = [b"sub", subscriber.key().as_ref(), &[subscription.plan_id]],
        bump = subscription.bump,
    )]
    pub subscription: Account<'info, Subscription>,
}

#[account]
#[derive(InitSpace)]
pub struct Plan {
    pub admin: Pubkey,
    pub plan_id: u8,
    pub price: u64,
    pub duration_seconds: i64,
    pub is_active: bool,
    pub subscriber_count: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Subscription {
    pub subscriber: Pubkey,
    pub plan_id: u8,
    pub started_at: i64,
    pub expires_at: i64,
    pub bump: u8,
}

#[event] pub struct Subscribed { pub subscriber: Pubkey, pub plan_id: u8, pub expires_at: i64 }

#[error_code]
pub enum SubError {
    #[msg("Plan is inactive")] PlanInactive,
    #[msg("Subscription expired")] Expired,
    #[msg("Math overflow")] MathOverflow,
}
```"""),
]

for name, question, answer in OSS_SEEDS:
    OSS.append((name, m(question, answer)))


# ═══════════════════════════════════════════════════════════════════════════════
# Write all outputs
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Evol-Instruct
    evol_records = [rec(content, method="evol-instruct", category=cat) for cat, content in EVOL]
    evol_path = OUT_DIR / "synthetic-evol-bulk.jsonl"
    c1 = write_jsonl(evol_records, evol_path)
    print(f"Evol-Instruct: {c1} records → {evol_path.name}")

    # DPO
    chosen_records = [rec(content, method="dpo-chosen", category=cat) for cat, content in DPO_CHOSEN]
    rejected_records = [rec(content, method="dpo-rejected", category=cat) for cat, content in DPO_REJECTED]
    chosen_path = OUT_DIR / "dpo-chosen-bulk.jsonl"
    rejected_path = OUT_DIR / "dpo-rejected-bulk.jsonl"
    c2 = write_jsonl(chosen_records, chosen_path)
    c3 = write_jsonl(rejected_records, rejected_path)
    print(f"DPO chosen: {c2} records → {chosen_path.name}")
    print(f"DPO rejected: {c3} records → {rejected_path.name}")

    # OSS-Instruct
    oss_records = [rec(content, method="oss-instruct", category=cat) for cat, content in OSS]
    oss_path = OUT_DIR / "synthetic-oss-bulk.jsonl"
    c4 = write_jsonl(oss_records, oss_path)
    print(f"OSS-Instruct: {c4} records → {oss_path.name}")

    print(f"\nTotal: {c1 + c2 + c3 + c4} records")


if __name__ == "__main__":
    main()
