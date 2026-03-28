#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 4: Migration, Metaplex, Jupiter, Helius, advanced Rust.

Target: ~200+ pairs from this file.
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


PAIRS = []

# ═══════════════════════════════════════════════════════════════════════════════
# Anchor Migration Patterns (old → new)
# ═══════════════════════════════════════════════════════════════════════════════

MIGRATIONS = [
    ("ctx.accounts.*.to_account_info().key()", "Use .key() directly",
     """```rust
// ❌ Old pattern (verbose)
let user_key = ctx.accounts.user.to_account_info().key();
let mint_key = ctx.accounts.mint.to_account_info().key();

// ✅ Modern Anchor (0.28+)
let user_key = ctx.accounts.user.key();
let mint_key = ctx.accounts.mint.key();
```
`.key()` is available directly on `Account`, `Signer`, `Program`, etc. No need for `.to_account_info()` first."""),

    ("Manual space calculation", "Use InitSpace derive macro",
     """```rust
// ❌ Old pattern (error-prone manual calculation)
#[account]
pub struct UserProfile {
    pub authority: Pubkey,     // 32
    pub name: String,          // 4 + len
    pub points: u64,           // 8
    pub is_active: bool,       // 1
}
const USER_PROFILE_SIZE: usize = 8 + 32 + (4 + 32) + 8 + 1; // easy to get wrong!

#[account(init, payer = user, space = USER_PROFILE_SIZE)]

// ✅ Modern Anchor (0.29+)
#[account]
#[derive(InitSpace)]
pub struct UserProfile {
    pub authority: Pubkey,
    #[max_len(32)]
    pub name: String,
    pub points: u64,
    pub is_active: bool,
}

#[account(init, payer = user, space = 8 + UserProfile::INIT_SPACE)]
```
`InitSpace` calculates the space automatically. Use `#[max_len(N)]` for Strings and Vecs."""),

    ("ctx.bumps.get(\"account_name\")", "Use ctx.bumps.account_name directly",
     """```rust
// ❌ Old pattern (Anchor < 0.29)
let bump = *ctx.bumps.get("my_account").unwrap();

// ✅ Modern Anchor (0.29+)
let bump = ctx.bumps.my_account;
```
`ctx.bumps` is now a struct with named fields instead of a HashMap. This catches typos at compile time."""),

    ("Pubkey::find_program_address", "Use seeds/bump in Anchor constraints",
     """```rust
// ❌ Old pattern (manual PDA derivation in instruction handler)
pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
    let (pda, bump) = Pubkey::find_program_address(
        &[b"vault", ctx.accounts.user.key().as_ref()],
        ctx.program_id,
    );
    require!(pda == ctx.accounts.vault.key(), MyError::InvalidPDA);
    // ...
}

// ✅ Modern Anchor — let constraints handle PDA validation
#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = user,
        space = 8 + Vault::INIT_SPACE,
        seeds = [b"vault", user.key().as_ref()],
        bump,
    )]
    pub vault: Account<'info, Vault>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```
Anchor's `seeds` + `bump` constraints handle PDA derivation and validation automatically."""),

    ("coral-xyz imports", "Use solana-foundation/anchor",
     """```toml
# ❌ Old Cargo.toml (references old GitHub org)
[dependencies]
anchor-lang = { git = "https://github.com/coral-xyz/anchor", tag = "v0.28.0" }

# ✅ Modern — use crates.io (recommended) or new GitHub org
[dependencies]
anchor-lang = "0.30.1"
anchor-spl = "0.30.1"
```

```json
// package.json — npm package name unchanged
{
  "dependencies": {
    "@coral-xyz/anchor": "^0.30.1"
  }
}
```
The Anchor repo moved to `solana-foundation/anchor` on GitHub. Use crates.io versions instead of git dependencies."""),

    ("try_from_slice for account deserialization", "Use Account<'info, T>",
     """```rust
// ❌ Old native pattern (manual deserialization)
let data = &ctx.accounts.my_account.try_borrow_data()?;
let account = MyAccount::try_from_slice(&data[8..])?; // skip discriminator

// ✅ Modern Anchor — automatic deserialization
#[derive(Accounts)]
pub struct MyInstruction<'info> {
    #[account(mut)]
    pub my_account: Account<'info, MyAccount>, // auto-deserialized
}

pub fn handler(ctx: Context<MyInstruction>) -> Result<()> {
    let account = &ctx.accounts.my_account; // already deserialized & validated
    Ok(())
}
```
`Account<'info, T>` handles discriminator checking, deserialization, and owner validation automatically."""),

    ("invoke_signed for PDA CPI", "Use CpiContext::new_with_signer",
     """```rust
// ❌ Old pattern (raw invoke_signed)
let seeds = &[b"vault".as_ref(), &[bump]];
invoke_signed(
    &spl_token::instruction::transfer(
        &spl_token::id(),
        source.key,
        destination.key,
        authority.key,
        &[],
        amount,
    )?,
    &[source.clone(), destination.clone(), authority.clone(), token_program.clone()],
    &[seeds],
)?;

// ✅ Modern Anchor (type-safe CPI)
let seeds = &[b"vault".as_ref(), &[vault.bump]];
token::transfer(
    CpiContext::new_with_signer(
        ctx.accounts.token_program.to_account_info(),
        Transfer {
            from: ctx.accounts.source.to_account_info(),
            to: ctx.accounts.destination.to_account_info(),
            authority: ctx.accounts.vault.to_account_info(),
        },
        &[seeds],
    ),
    amount,
)?;
```
Anchor's CPI helpers are type-safe and catch account mismatches at compile time."""),
]

for old_pattern, new_pattern, code in MIGRATIONS:
    q = f"How do I migrate from `{old_pattern}` to `{new_pattern}` in modern Anchor?"
    PAIRS.append(("migration", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Metaplex Integration
# ═══════════════════════════════════════════════════════════════════════════════

METAPLEX = [
    ("create an NFT with Metaplex metadata",
     """Use the `mpl-token-metadata` crate with Anchor for NFT metadata:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token, TokenAccount, MintTo, self};
use anchor_spl::associated_token::AssociatedToken;
use mpl_token_metadata::instructions::{
    CreateMetadataAccountV3CpiBuilder,
    CreateMasterEditionV3CpiBuilder,
};

#[program]
pub mod nft_creator {
    use super::*;

    pub fn create_nft(
        ctx: Context<CreateNft>,
        name: String,
        symbol: String,
        uri: String,
    ) -> Result<()> {
        // 1. Mint one token
        token::mint_to(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), MintTo {
                mint: ctx.accounts.mint.to_account_info(),
                to: ctx.accounts.token_account.to_account_info(),
                authority: ctx.accounts.creator.to_account_info(),
            }),
            1,
        )?;

        // 2. Create metadata account via CPI to Metaplex
        CreateMetadataAccountV3CpiBuilder::new(
            &ctx.accounts.token_metadata_program.to_account_info(),
        )
        .metadata(&ctx.accounts.metadata.to_account_info())
        .mint(&ctx.accounts.mint.to_account_info())
        .mint_authority(&ctx.accounts.creator.to_account_info())
        .payer(&ctx.accounts.creator.to_account_info())
        .update_authority(&ctx.accounts.creator.to_account_info(), true)
        .system_program(&ctx.accounts.system_program.to_account_info())
        .data(mpl_token_metadata::types::DataV2 {
            name,
            symbol,
            uri,
            seller_fee_basis_points: 500, // 5% royalty
            creators: Some(vec![mpl_token_metadata::types::Creator {
                address: ctx.accounts.creator.key(),
                verified: true,
                share: 100,
            }]),
            collection: None,
            uses: None,
        })
        .is_mutable(true)
        .invoke()?;

        // 3. Create master edition (makes it a true NFT — max supply 0)
        CreateMasterEditionV3CpiBuilder::new(
            &ctx.accounts.token_metadata_program.to_account_info(),
        )
        .edition(&ctx.accounts.master_edition.to_account_info())
        .mint(&ctx.accounts.mint.to_account_info())
        .update_authority(&ctx.accounts.creator.to_account_info())
        .mint_authority(&ctx.accounts.creator.to_account_info())
        .payer(&ctx.accounts.creator.to_account_info())
        .metadata(&ctx.accounts.metadata.to_account_info())
        .token_program(&ctx.accounts.token_program.to_account_info())
        .system_program(&ctx.accounts.system_program.to_account_info())
        .max_supply(0) // 0 = unique NFT, no prints allowed
        .invoke()?;

        Ok(())
    }
}
```

Dependencies in Cargo.toml:
```toml
[dependencies]
mpl-token-metadata = "4.1"
```"""),

    ("verify an NFT belongs to a Metaplex collection",
     """```rust
use mpl_token_metadata::accounts::Metadata;
use mpl_token_metadata::types::Collection;

pub fn verify_collection(
    metadata_account: &AccountInfo,
    expected_collection: &Pubkey,
) -> Result<()> {
    let metadata = Metadata::safe_deserialize(&metadata_account.data.borrow())?;

    match metadata.collection {
        Some(collection) => {
            require!(collection.verified, NftError::CollectionNotVerified);
            require!(
                collection.key == *expected_collection,
                NftError::WrongCollection
            );
            Ok(())
        }
        None => Err(error!(NftError::NoCollection)),
    }
}

#[derive(Accounts)]
pub struct CollectionGated<'info> {
    pub holder: Signer<'info>,
    #[account(
        constraint = token_account.amount == 1 @ NftError::NotHolder,
        constraint = token_account.owner == holder.key() @ NftError::NotOwner,
    )]
    pub token_account: Account<'info, TokenAccount>,
    /// CHECK: Validated by Metaplex metadata deserialization
    #[account(
        seeds = [
            b"metadata",
            mpl_token_metadata::ID.as_ref(),
            token_account.mint.as_ref(),
        ],
        bump,
        seeds::program = mpl_token_metadata::ID,
    )]
    pub metadata: UncheckedAccount<'info>,
}
```

The metadata PDA is derived from `["metadata", metaplex_program_id, mint]`. Always check `collection.verified == true` to prevent fake collection assignments."""),
]

for desc, code in METAPLEX:
    q = f"How do I {desc} using Anchor?"
    PAIRS.append(("metaplex", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Jupiter Integration (TypeScript)
# ═══════════════════════════════════════════════════════════════════════════════

JUPITER = [
    ("perform a token swap using Jupiter",
     """```typescript
import { Connection, Keypair, VersionedTransaction } from "@solana/web3.js";

const connection = new Connection("https://api.mainnet-beta.solana.com");

async function jupiterSwap(
  inputMint: string,
  outputMint: string,
  amount: number, // in smallest units (lamports for SOL)
  userKeypair: Keypair,
  slippageBps: number = 50 // 0.5%
) {
  // 1. Get quote
  const quoteUrl = `https://quote-api.jup.ag/v6/quote?` +
    `inputMint=${inputMint}&outputMint=${outputMint}` +
    `&amount=${amount}&slippageBps=${slippageBps}`;
  const quoteResponse = await fetch(quoteUrl);
  const quote = await quoteResponse.json();

  console.log(`Route: ${quote.routePlan.map(r => r.swapInfo.label).join(" → ")}`);
  console.log(`Expected output: ${quote.outAmount}`);

  // 2. Get swap transaction
  const swapResponse = await fetch("https://quote-api.jup.ag/v6/swap", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quoteResponse: quote,
      userPublicKey: userKeypair.publicKey.toBase58(),
      wrapAndUnwrapSol: true,
      dynamicComputeUnitLimit: true,
      prioritizationFeeLamports: "auto",
    }),
  });
  const { swapTransaction } = await swapResponse.json();

  // 3. Deserialize, sign, and send
  const txBuf = Buffer.from(swapTransaction, "base64");
  const tx = VersionedTransaction.deserialize(txBuf);
  tx.sign([userKeypair]);

  const sig = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    maxRetries: 2,
  });

  const confirmation = await connection.confirmTransaction(sig, "confirmed");
  console.log(`Swap confirmed: ${sig}`);
  return sig;
}

// Example: Swap 0.1 SOL to USDC
const SOL_MINT = "So11111111111111111111111111111111111111112";
const USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
await jupiterSwap(SOL_MINT, USDC_MINT, 100_000_000, wallet);
```

Key points:
- Jupiter aggregates across all Solana DEXs for best price
- `slippageBps`: 50 = 0.5% slippage tolerance
- `wrapAndUnwrapSol`: automatically wraps/unwraps SOL ↔ wSOL
- Always use versioned transactions (Jupiter returns v0)"""),

    ("get the best swap route from Jupiter with price impact",
     """```typescript
async function getSwapQuote(
  inputMint: string,
  outputMint: string,
  amount: number,
) {
  const url = new URL("https://quote-api.jup.ag/v6/quote");
  url.searchParams.set("inputMint", inputMint);
  url.searchParams.set("outputMint", outputMint);
  url.searchParams.set("amount", amount.toString());
  url.searchParams.set("slippageBps", "50");
  url.searchParams.set("onlyDirectRoutes", "false");
  url.searchParams.set("asLegacyTransaction", "false");

  const response = await fetch(url.toString());
  const quote = await response.json();

  return {
    inputAmount: quote.inAmount,
    outputAmount: quote.outAmount,
    priceImpactPct: quote.priceImpactPct,
    routePlan: quote.routePlan.map((r: any) => ({
      dex: r.swapInfo.label,
      inputMint: r.swapInfo.inputMint,
      outputMint: r.swapInfo.outputMint,
      percentage: r.percent,
    })),
    otherAmountThreshold: quote.otherAmountThreshold, // min output accounting for slippage
  };
}
```

Check `priceImpactPct` before executing — values above 1% indicate low liquidity."""),
]

for desc, code in JUPITER:
    q = f"How do I {desc}?"
    PAIRS.append(("jupiter", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Helius API Integration
# ═══════════════════════════════════════════════════════════════════════════════

HELIUS = [
    ("fetch parsed transaction history using Helius",
     """```typescript
const HELIUS_API_KEY = process.env.HELIUS_API_KEY;

async function getTransactionHistory(address: string, limit: number = 10) {
  const url = `https://api.helius.xyz/v0/addresses/${address}/transactions?api-key=${HELIUS_API_KEY}&limit=${limit}`;
  const response = await fetch(url);
  const transactions = await response.json();

  return transactions.map((tx: any) => ({
    signature: tx.signature,
    type: tx.type, // e.g., "SWAP", "TRANSFER", "NFT_SALE"
    timestamp: tx.timestamp,
    fee: tx.fee,
    description: tx.description,
    tokenTransfers: tx.tokenTransfers?.map((t: any) => ({
      mint: t.mint,
      amount: t.tokenAmount,
      from: t.fromUserAccount,
      to: t.toUserAccount,
    })),
    nativeTransfers: tx.nativeTransfers?.map((t: any) => ({
      from: t.fromUserAccount,
      to: t.toUserAccount,
      amount: t.amount / 1e9, // Convert lamports to SOL
    })),
  }));
}
```

Helius parses raw transaction data into human-readable types (SWAP, TRANSFER, NFT_SALE, etc.) — much easier than parsing raw instruction data."""),

    ("use Helius webhooks for real-time events",
     """```typescript
// Register a webhook via Helius API
async function createWebhook(addresses: string[], webhookUrl: string) {
  const response = await fetch(
    `https://api.helius.xyz/v0/webhooks?api-key=${HELIUS_API_KEY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        webhookURL: webhookUrl,
        transactionTypes: ["TRANSFER", "SWAP", "NFT_SALE"],
        accountAddresses: addresses,
        webhookType: "enhanced", // parsed transactions
      }),
    }
  );
  return response.json();
}

// Express handler for incoming webhooks
import express from "express";
const app = express();
app.use(express.json());

app.post("/helius-webhook", (req, res) => {
  const events = req.body;
  for (const event of events) {
    console.log(`Type: ${event.type}`);
    console.log(`Signature: ${event.signature}`);
    console.log(`Description: ${event.description}`);

    if (event.type === "TRANSFER") {
      const transfers = event.nativeTransfers || [];
      for (const t of transfers) {
        console.log(`  ${t.fromUserAccount} → ${t.toUserAccount}: ${t.amount / 1e9} SOL`);
      }
    }
  }
  res.status(200).send("OK");
});
```

Helius webhooks push parsed events in real-time — no polling needed. Use `enhanced` type for human-readable parsed data."""),

    ("get token balances and metadata using Helius DAS API",
     """```typescript
async function getTokenBalances(ownerAddress: string) {
  const response = await fetch(
    `https://mainnet.helius-rpc.com/?api-key=${HELIUS_API_KEY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "get-assets",
        method: "getAssetsByOwner",
        params: {
          ownerAddress,
          page: 1,
          limit: 100,
          displayOptions: {
            showFungible: true,
            showNativeBalance: true,
          },
        },
      }),
    }
  );
  const { result } = await response.json();

  return {
    nativeBalance: result.nativeBalance?.lamports / 1e9,
    tokens: result.items.map((item: any) => ({
      mint: item.id,
      name: item.content?.metadata?.name,
      symbol: item.content?.metadata?.symbol,
      balance: item.token_info?.balance,
      decimals: item.token_info?.decimals,
      imageUri: item.content?.links?.image,
    })),
  };
}
```

The DAS (Digital Asset Standard) API provides rich asset metadata including images, attributes, and collection info in a single call."""),
]

for desc, code in HELIUS:
    q = f"How do I {desc}?"
    PAIRS.append(("helius-api", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Program Upgrades & Deployment
# ═══════════════════════════════════════════════════════════════════════════════

DEPLOYMENT = [
    ("deploy and upgrade an Anchor program",
     """```bash
# First deployment
anchor build
anchor deploy --provider.cluster devnet

# Subsequent upgrades
anchor build
anchor upgrade target/deploy/my_program.so --program-id <PROGRAM_ID> --provider.cluster devnet

# Or using solana CLI directly
solana program deploy target/deploy/my_program.so --program-id <PROGRAM_ID>
```

**Upgrade safety checklist:**
1. Never change account struct layouts without a migration plan
2. New fields must be added at the END of structs
3. Don't remove or reorder existing fields
4. Test the upgrade on devnet first
5. Consider using a multisig for upgrade authority

```bash
# Transfer upgrade authority to a multisig
solana program set-upgrade-authority <PROGRAM_ID> --new-upgrade-authority <MULTISIG_ADDRESS>

# Make program immutable (irreversible!)
solana program set-upgrade-authority <PROGRAM_ID> --final
```"""),

    ("implement account migration after a program upgrade",
     """```rust
use anchor_lang::prelude::*;

// Old account layout (v1)
#[account]
pub struct UserAccountV1 {
    pub authority: Pubkey,
    pub balance: u64,
    pub bump: u8,
}

// New account layout (v2) — adds new fields at the end
#[account]
#[derive(InitSpace)]
pub struct UserAccountV2 {
    pub authority: Pubkey,
    pub balance: u64,
    pub bump: u8,
    // New fields:
    pub reputation: u64,
    pub created_at: i64,
    pub version: u8,
}

#[program]
pub mod my_program {
    use super::*;

    pub fn migrate_account(ctx: Context<MigrateAccount>) -> Result<()> {
        let account = &mut ctx.accounts.user_account;

        // Only migrate if not already v2
        require!(account.version == 0, MyError::AlreadyMigrated);

        // Set new fields with defaults
        account.reputation = 0;
        account.created_at = Clock::get()?.unix_timestamp;
        account.version = 2;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct MigrateAccount<'info> {
    pub authority: Signer<'info>,
    #[account(
        mut,
        realloc = 8 + UserAccountV2::INIT_SPACE,
        realloc::payer = authority,
        realloc::zero = false,
        has_one = authority,
    )]
    pub user_account: Account<'info, UserAccountV2>,
    pub system_program: Program<'info, System>,
}
```

Migration pattern:
1. Add new fields at the END of the struct
2. Use `realloc` to grow the account
3. Add a `version` field to track migration status
4. Allow users to self-migrate or batch-migrate via admin"""),
]

for desc, code in DEPLOYMENT:
    q = f"How do I {desc}?"
    PAIRS.append(("deployment", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Advanced Rust patterns for Solana
# ═══════════════════════════════════════════════════════════════════════════════

RUST_PATTERNS = [
    ("use generic constraints in Anchor programs",
     """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{Token, TokenAccount, Mint, Transfer, self};

// Generic deposit function that works with any token
pub fn deposit<'info>(
    token_program: &Program<'info, Token>,
    from: &Account<'info, TokenAccount>,
    to: &Account<'info, TokenAccount>,
    authority: &Signer<'info>,
    amount: u64,
) -> Result<()> {
    token::transfer(
        CpiContext::new(
            token_program.to_account_info(),
            Transfer {
                from: from.to_account_info(),
                to: to.to_account_info(),
                authority: authority.to_account_info(),
            },
        ),
        amount,
    )
}
```

Extract common operations into helper functions. In Anchor, you typically pass account references as parameters rather than using Rust generics, since account types are concrete."""),

    ("implement custom serialization for complex types",
     """```rust
use anchor_lang::prelude::*;

// Custom enum with associated data
#[derive(AnchorSerialize, AnchorDeserialize, Clone, PartialEq, Eq)]
pub enum OrderType {
    Market,
    Limit { price: u64 },
    StopLoss { trigger_price: u64, limit_price: u64 },
}

// InitSpace requires manual implementation for complex enums
impl anchor_lang::Space for OrderType {
    const INIT_SPACE: usize = 1 + 8 + 8; // tag + max variant size
}

#[account]
#[derive(InitSpace)]
pub struct Order {
    pub owner: Pubkey,
    pub order_type: OrderType,
    pub amount: u64,
    pub filled: u64,
    pub bump: u8,
}

// Use in instruction handler
pub fn place_order(ctx: Context<PlaceOrder>, order_type: OrderType, amount: u64) -> Result<()> {
    match &order_type {
        OrderType::Market => {
            // Execute immediately at market price
        }
        OrderType::Limit { price } => {
            require!(*price > 0, OrderError::InvalidPrice);
            // Place limit order
        }
        OrderType::StopLoss { trigger_price, limit_price } => {
            require!(trigger_price > limit_price, OrderError::InvalidStopLoss);
            // Place stop-loss order
        }
    }

    let order = &mut ctx.accounts.order;
    order.owner = ctx.accounts.owner.key();
    order.order_type = order_type;
    order.amount = amount;
    order.filled = 0;
    Ok(())
}
```

For enums with associated data, implement `Space` manually — the compiler can't auto-derive it. Use the maximum variant size."""),

    ("use trait objects for extensible program design",
     """```rust
use anchor_lang::prelude::*;

// Define a trait for different fee strategies
pub trait FeeStrategy {
    fn calculate_fee(&self, amount: u64) -> Result<u64>;
}

pub struct FlatFee {
    pub fee: u64,
}

impl FeeStrategy for FlatFee {
    fn calculate_fee(&self, _amount: u64) -> Result<u64> {
        Ok(self.fee)
    }
}

pub struct PercentageFee {
    pub bps: u16,
}

impl FeeStrategy for PercentageFee {
    fn calculate_fee(&self, amount: u64) -> Result<u64> {
        Ok((amount as u128)
            .checked_mul(self.bps as u128)
            .ok_or(error!(MyError::Overflow))?
            .checked_div(10_000)
            .ok_or(error!(MyError::Overflow))? as u64)
    }
}

pub struct TieredFee {
    pub tiers: [(u64, u16); 3], // (threshold, bps)
}

impl FeeStrategy for TieredFee {
    fn calculate_fee(&self, amount: u64) -> Result<u64> {
        let bps = self.tiers.iter()
            .rev()
            .find(|(threshold, _)| amount >= *threshold)
            .map(|(_, bps)| *bps)
            .unwrap_or(self.tiers[0].1);

        Ok((amount as u128)
            .checked_mul(bps as u128)
            .ok_or(error!(MyError::Overflow))?
            .checked_div(10_000)
            .ok_or(error!(MyError::Overflow))? as u64)
    }
}

// Usage in program:
fn apply_fee(fee_type: u8, amount: u64) -> Result<u64> {
    match fee_type {
        0 => FlatFee { fee: 5000 }.calculate_fee(amount),
        1 => PercentageFee { bps: 30 }.calculate_fee(amount),
        2 => TieredFee {
            tiers: [(0, 50), (1_000_000, 30), (100_000_000, 10)],
        }.calculate_fee(amount),
        _ => err!(MyError::InvalidFeeType),
    }
}
```

Trait-based design keeps fee logic modular and testable. Store the fee type in the config account and dispatch at runtime."""),

    ("use const generics for fixed-size collections",
     """```rust
use anchor_lang::prelude::*;

// Const generic for configurable-size pools
#[account]
pub struct Pool<const N: usize> {
    pub authority: Pubkey,
    pub mints: [Pubkey; N],
    pub reserves: [u64; N],
    pub weights: [u16; N], // basis points, must sum to 10000
    pub bump: u8,
}

// Unfortunately, Anchor doesn't fully support const generics in #[account]
// Instead, use fixed sizes with different type aliases:

#[account]
#[derive(InitSpace)]
pub struct Pool2 {
    pub authority: Pubkey,
    pub mints: [Pubkey; 2],
    pub reserves: [u64; 2],
    pub weights: [u16; 2],
    pub swap_fee_bps: u16,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Pool4 {
    pub authority: Pubkey,
    pub mints: [Pubkey; 4],
    pub reserves: [u64; 4],
    pub weights: [u16; 4],
    pub swap_fee_bps: u16,
    pub bump: u8,
}

// Shared logic via trait
pub trait PoolOps {
    fn validate_weights(&self) -> Result<()>;
    fn calculate_swap(&self, input_idx: usize, output_idx: usize, amount_in: u64) -> Result<u64>;
}

impl PoolOps for Pool2 {
    fn validate_weights(&self) -> Result<()> {
        let sum: u32 = self.weights.iter().map(|w| *w as u32).sum();
        require!(sum == 10_000, PoolError::InvalidWeights);
        Ok(())
    }

    fn calculate_swap(&self, input_idx: usize, output_idx: usize, amount_in: u64) -> Result<u64> {
        require!(input_idx < 2 && output_idx < 2, PoolError::InvalidIndex);
        require!(input_idx != output_idx, PoolError::SameToken);
        // Weighted constant product formula...
        Ok(0) // simplified
    }
}
```"""),

    ("handle optional accounts in Anchor",
     """```rust
use anchor_lang::prelude::*;

#[derive(Accounts)]
pub struct OptionalTransfer<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(mut)]
    pub vault: Account<'info, Vault>,

    // Optional: referrer gets a bonus if provided
    /// CHECK: Optional referrer account
    pub referrer: Option<UncheckedAccount<'info>>,

    // Optional: only needed for token transfers
    pub token_program: Option<Program<'info, Token>>,
}

pub fn transfer_with_optional_referral(
    ctx: Context<OptionalTransfer>,
    amount: u64,
) -> Result<()> {
    let vault = &mut ctx.accounts.vault;

    // Handle optional referrer
    if let Some(referrer) = &ctx.accounts.referrer {
        let referral_bonus = amount.checked_div(100).ok_or(MyError::MathOverflow)?; // 1%
        // Credit referrer...
        msg!("Referral bonus to {}: {}", referrer.key(), referral_bonus);
    }

    vault.balance = vault.balance.checked_add(amount).ok_or(MyError::MathOverflow)?;
    Ok(())
}
```

`Option<T>` accounts are `None` if the account is not provided (defaults to the program ID). Use `if let Some(account) = &ctx.accounts.field` to handle."""),
]

for desc, code in RUST_PATTERNS:
    q = f"How do I {desc}?"
    PAIRS.append(("rust-patterns", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Error handling deep-dives
# ═══════════════════════════════════════════════════════════════════════════════

ERROR_DEEP = [
    ("decode Solana transaction errors",
     """Common Solana error codes and what they mean:

```
// Program-level errors (your custom errors start at 6000)
Error Code   | Meaning
-------------|------------------------------------------
0x0          | Custom error 0 (your first error variant)
0x1          | Custom error 1
6000 (0x1770)| First Anchor custom error
6001-6XXX    | Your subsequent #[error_code] variants

// Anchor framework errors (starts at 3000)
3000 | AccountDiscriminatorAlreadySet
3001 | AccountDiscriminatorNotFound
3002 | AccountDidNotDeserialize
3003 | AccountDidNotSerialize
3004 | AccountNotEnoughKeys
3005 | AccountNotMutable
3006 | AccountOwnedByWrongProgram
3007 | InvalidProgramId
3008 | InvalidProgramExecutable
3009 | AccountNotSigner
3010 | AccountNotSystemOwned
3012 | AccountNotInitialized
3014 | AccountNotProgramData

// Constraint errors (2000+)
2000 | ConstraintMut
2001 | ConstraintHasOne
2003 | ConstraintSigner
2006 | ConstraintSeeds
2007 | ConstraintMint
2009 | ConstraintAssociated
2012 | ConstraintOwner
2015 | ConstraintSpace
2016 | ConstraintAccountIsNone

// SPL Token errors
1 | InsufficientFunds
3 | InvalidAccountData
4 | InvalidOwner
```

```typescript
// Parse error codes in TypeScript
try { await tx.rpc(); } catch (err) {
  if (err instanceof anchor.AnchorError) {
    console.log(`Error ${err.error.errorCode.number}: ${err.error.errorCode.code}`);
    console.log(err.error.errorMessage);
  }
}
```"""),

    ("implement comprehensive error handling in a Solana program",
     """```rust
use anchor_lang::prelude::*;

// Organize errors by category
#[error_code]
pub enum AppError {
    // Authorization (6000-6009)
    #[msg("You are not authorized to perform this action")]
    Unauthorized,
    #[msg("Missing required signer")]
    MissingSigner,
    #[msg("Admin privileges required")]
    AdminRequired,

    // Validation (6010-6019)
    #[msg("Amount must be greater than zero")]
    ZeroAmount,
    #[msg("Amount exceeds maximum allowed")]
    ExceedsMaximum,
    #[msg("Invalid parameter value")]
    InvalidParameter,
    #[msg("String exceeds maximum length")]
    StringTooLong,

    // State (6020-6029)
    #[msg("Account already initialized")]
    AlreadyInitialized,
    #[msg("Invalid state transition")]
    InvalidStateTransition,
    #[msg("Operation not allowed in current state")]
    InvalidState,

    // Math (6030-6039)
    #[msg("Arithmetic overflow")]
    MathOverflow,
    #[msg("Division by zero")]
    DivisionByZero,
    #[msg("Insufficient balance")]
    InsufficientBalance,

    // External (6040-6049)
    #[msg("Oracle price is stale")]
    StalePriceFeed,
    #[msg("Price deviation too high")]
    PriceDeviationTooHigh,
}

// Usage patterns:
pub fn example(ctx: Context<Example>, amount: u64) -> Result<()> {
    // require! for simple boolean checks
    require!(amount > 0, AppError::ZeroAmount);
    require!(amount <= 1_000_000_000, AppError::ExceedsMaximum);

    // require_keys_eq! for pubkey comparison
    require_keys_eq!(
        ctx.accounts.vault.authority,
        ctx.accounts.authority.key(),
        AppError::Unauthorized
    );

    // err! for early returns
    if some_complex_condition() {
        return err!(AppError::InvalidState);
    }

    // Constraint with error
    // #[account(constraint = vault.is_active @ AppError::InvalidState)]

    Ok(())
}
```

Anchor error codes start at 6000. Organize by category with comment headers. Always use descriptive `#[msg]` — they appear in transaction logs and client errors."""),
]

for desc, code in ERROR_DEEP:
    q = f"How do I {desc}?"
    PAIRS.append(("error-handling", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Solana Program Library (SPL) patterns
# ═══════════════════════════════════════════════════════════════════════════════

SPL_PATTERNS = [
    ("create a token with Token-2022 transfer hook",
     """```rust
// Transfer hooks allow custom logic on every token transfer.
// The hook program is invoked automatically by Token-2022.

use anchor_lang::prelude::*;
use spl_transfer_hook_interface::instruction::ExecuteInstruction;

declare_id!("HookProgramId11111111111111111111111111111");

#[program]
pub mod transfer_hook {
    use super::*;

    // This function is called by Token-2022 on every transfer
    pub fn transfer_hook(ctx: Context<TransferHook>, amount: u64) -> Result<()> {
        // Example: enforce transfer restrictions
        let whitelist = &ctx.accounts.whitelist;

        // Check sender is whitelisted
        let sender_whitelisted = whitelist.members[..whitelist.count as usize]
            .iter()
            .any(|m| *m == ctx.accounts.source_authority.key());

        require!(sender_whitelisted, HookError::NotWhitelisted);

        msg!("Transfer hook: {} tokens approved", amount);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct TransferHook<'info> {
    /// CHECK: Source token account
    pub source: UncheckedAccount<'info>,
    pub mint: InterfaceAccount<'info, Mint>,
    /// CHECK: Destination token account
    pub destination: UncheckedAccount<'info>,
    /// CHECK: Source authority
    pub source_authority: UncheckedAccount<'info>,
    /// CHECK: Extra account meta list PDA
    pub extra_metas: UncheckedAccount<'info>,
    #[account(seeds = [b"whitelist"], bump)]
    pub whitelist: Account<'info, Whitelist>,
}
```

Transfer hooks enable:
- Transfer restrictions (whitelists, blacklists, KYC)
- Automatic royalty enforcement
- Transfer taxes/fees
- Custom accounting on every transfer"""),

    ("implement a token faucet for testing",
     """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, MintTo, Token, TokenAccount};
use anchor_spl::associated_token::AssociatedToken;

const MAX_DRIP: u64 = 1_000_000_000; // 1000 tokens (6 decimals)
const COOLDOWN: i64 = 3600; // 1 hour between drips

#[program]
pub mod faucet {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let faucet = &mut ctx.accounts.faucet;
        faucet.admin = ctx.accounts.admin.key();
        faucet.mint = ctx.accounts.mint.key();
        faucet.total_dripped = 0;
        faucet.bump = ctx.bumps.faucet;
        Ok(())
    }

    pub fn drip(ctx: Context<Drip>, amount: u64) -> Result<()> {
        require!(amount <= MAX_DRIP, FaucetError::TooMuch);

        let clock = Clock::get()?;
        let user_state = &mut ctx.accounts.user_state;

        let elapsed = clock.unix_timestamp
            .checked_sub(user_state.last_drip).ok_or(FaucetError::MathOverflow)?;
        require!(elapsed >= COOLDOWN, FaucetError::CooldownActive);

        // Mint tokens (PDA is mint authority)
        let seeds = &[b"faucet".as_ref(), &[ctx.accounts.faucet.bump]];
        token::mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                MintTo {
                    mint: ctx.accounts.mint.to_account_info(),
                    to: ctx.accounts.user_ata.to_account_info(),
                    authority: ctx.accounts.faucet.to_account_info(),
                },
                &[seeds],
            ),
            amount,
        )?;

        user_state.last_drip = clock.unix_timestamp;
        user_state.total_received = user_state.total_received
            .checked_add(amount).ok_or(FaucetError::MathOverflow)?;

        let faucet = &mut ctx.accounts.faucet;
        faucet.total_dripped = faucet.total_dripped
            .checked_add(amount).ok_or(FaucetError::MathOverflow)?;

        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Faucet {
    pub admin: Pubkey,
    pub mint: Pubkey,
    pub total_dripped: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct UserFaucetState {
    pub user: Pubkey,
    pub last_drip: i64,
    pub total_received: u64,
    pub bump: u8,
}
```

The faucet PDA is set as the mint authority. Each user gets one drip per cooldown period, tracked via a per-user PDA."""),
]

for desc, code in SPL_PATTERNS:
    q = f"How do I {desc}?"
    PAIRS.append(("spl-patterns", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Solana native program interactions
# ═══════════════════════════════════════════════════════════════════════════════

NATIVE = [
    ("use the Ed25519 program for signature verification",
     """```rust
use anchor_lang::prelude::*;
use anchor_lang::solana_program::{
    ed25519_program,
    sysvar::instructions::{self, get_instruction_relative},
};

pub fn verify_signature(ctx: Context<VerifySignature>) -> Result<()> {
    // The Ed25519 verify instruction must be in the SAME transaction,
    // typically as the instruction right before this one.

    let ix = get_instruction_relative(-1, &ctx.accounts.instruction_sysvar)?;

    // Verify it's an Ed25519 program instruction
    require!(
        ix.program_id == ed25519_program::id(),
        MyError::InvalidInstruction
    );

    // Parse the Ed25519 instruction data
    // Format: num_signatures (u8) | padding (u8) | sig_offset (u16) | ...
    require!(ix.data.len() >= 2, MyError::InvalidInstructionData);

    let num_signatures = ix.data[0];
    require!(num_signatures == 1, MyError::InvalidSignatureCount);

    msg!("Ed25519 signature verified!");
    Ok(())
}

#[derive(Accounts)]
pub struct VerifySignature<'info> {
    /// CHECK: Instructions sysvar
    #[account(address = instructions::id())]
    pub instruction_sysvar: UncheckedAccount<'info>,
}
```

```typescript
// Client-side: build transaction with Ed25519 verify + your instruction
import { Ed25519Program } from "@solana/web3.js";

const ed25519Ix = Ed25519Program.createInstructionWithPublicKey({
    publicKey: signerPublicKey.toBytes(),
    message: messageBytes,
    signature: signatureBytes,
});

const tx = new Transaction().add(ed25519Ix).add(programIx);
```

The Ed25519 program verifies signatures off-chain style. Useful for gasless transactions, oracle signatures, and off-chain authorization."""),

    ("access sysvars in an Anchor program",
     """```rust
use anchor_lang::prelude::*;
use anchor_lang::solana_program::sysvar;

pub fn read_sysvars(ctx: Context<ReadSysvars>) -> Result<()> {
    // Clock — current slot, epoch, timestamp
    let clock = Clock::get()?;
    msg!("Slot: {}", clock.slot);
    msg!("Timestamp: {}", clock.unix_timestamp);
    msg!("Epoch: {}", clock.epoch);

    // Rent — current rent rates
    let rent = Rent::get()?;
    msg!("Min balance for 100 bytes: {}", rent.minimum_balance(100));

    // EpochSchedule — epoch timing info
    let epoch_schedule = EpochSchedule::get()?;
    msg!("Slots per epoch: {}", epoch_schedule.slots_per_epoch);

    Ok(())
}

// For sysvars not available via get(), pass as account:
#[derive(Accounts)]
pub struct WithSysvars<'info> {
    /// CHECK: Recent slot hashes sysvar
    #[account(address = sysvar::slot_hashes::id())]
    pub slot_hashes: UncheckedAccount<'info>,

    /// CHECK: Instructions sysvar (for introspection)
    #[account(address = sysvar::instructions::id())]
    pub instructions: UncheckedAccount<'info>,

    /// CHECK: Stake history
    #[account(address = sysvar::stake_history::id())]
    pub stake_history: UncheckedAccount<'info>,
}
```

Sysvars available via `get()` (no account needed): Clock, Rent, EpochSchedule, Fees (deprecated).
Sysvars requiring account: SlotHashes, Instructions, StakeHistory, RecentBlockhashes (deprecated)."""),
]

for desc, code in NATIVE:
    q = f"How do I {desc}?"
    PAIRS.append(("native-programs", m(q, code)))


# ═══════════════════════════════════════════════════════════════════════════════
# Write output
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = [rec(content, category=cat) for cat, content in PAIRS]
    out_path = OUT_DIR / "synthetic-bulk4.jsonl"
    count = write_jsonl(records, out_path)
    print(f"Generated {count} records → {out_path}")


if __name__ == "__main__":
    main()
