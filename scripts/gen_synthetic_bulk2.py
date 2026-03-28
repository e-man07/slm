#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 2: TypeScript client, testing, DeFi, security, concepts.

Target: ~400 pairs from this file.
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
# TypeScript Client Patterns
# ═══════════════════════════════════════════════════════════════════════════════

TS_PATTERNS = [
    ("send a transaction with Anchor",
     """```typescript
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { MyProgram } from "../target/types/my_program";

const provider = anchor.AnchorProvider.env();
anchor.setProvider(provider);
const program = anchor.workspace.MyProgram as Program<MyProgram>;

const tx = await program.methods
  .initialize()
  .accounts({
    user: provider.wallet.publicKey,
    systemProgram: anchor.web3.SystemProgram.programId,
  })
  .rpc();

console.log("Transaction signature:", tx);
```

The Anchor TS client auto-generates typed methods from your IDL. `.methods.initialize()` matches the `initialize` instruction, `.accounts()` takes the required accounts, and `.rpc()` sends the transaction."""),

    ("derive a PDA on the client side",
     """```typescript
const [pda, bump] = anchor.web3.PublicKey.findProgramAddressSync(
  [
    Buffer.from("user-account"),
    provider.wallet.publicKey.toBuffer(),
  ],
  program.programId
);

// Use in transaction
const tx = await program.methods
  .initialize()
  .accounts({
    userAccount: pda,
    user: provider.wallet.publicKey,
    systemProgram: anchor.web3.SystemProgram.programId,
  })
  .rpc();
```

Seeds must match exactly what's in the Rust program. Use `Buffer.from("string")` for string seeds, `.toBuffer()` for pubkeys, and `new anchor.BN(number).toArrayLike(Buffer, "le", 8)` for u64."""),

    ("fetch and deserialize an account",
     """```typescript
// Fetch a single account
const account = await program.account.userProfile.fetch(accountPubkey);
console.log("Username:", account.username);
console.log("Reputation:", account.reputation.toNumber());

// Fetch all accounts of a type
const allAccounts = await program.account.userProfile.all();
for (const { publicKey, account } of allAccounts) {
  console.log(`${publicKey.toBase58()}: ${account.username}`);
}

// Fetch with filters
const filtered = await program.account.userProfile.all([
  {
    memcmp: {
      offset: 8, // skip discriminator
      bytes: provider.wallet.publicKey.toBase58(),
    },
  },
]);
```

Anchor auto-deserializes accounts using the IDL. `BN` values from u64/i64 fields need `.toNumber()` for JS numbers (careful with values > 2^53)."""),

    ("send a transaction with priority fees",
     """```typescript
import { ComputeBudgetProgram } from "@solana/web3.js";

const modifyComputeUnits = ComputeBudgetProgram.setComputeUnitLimit({
  units: 300_000,
});
const addPriorityFee = ComputeBudgetProgram.setComputeUnitPrice({
  microLamports: 50_000, // priority fee per CU
});

const tx = await program.methods
  .swap(new anchor.BN(1_000_000))
  .accounts({ /* ... */ })
  .preInstructions([modifyComputeUnits, addPriorityFee])
  .rpc();
```

Use `setComputeUnitPrice` for priority fees (in micro-lamports per CU). Use `setComputeUnitLimit` to set max CU. Add them as `preInstructions` so they execute before your instruction."""),

    ("handle transaction errors",
     """```typescript
try {
  const tx = await program.methods.riskyOperation().accounts({/* ... */}).rpc();
} catch (err) {
  if (err instanceof anchor.AnchorError) {
    console.log("Error code:", err.error.errorCode.code);
    console.log("Error message:", err.error.errorMessage);
    console.log("Error number:", err.error.errorCode.number);
    // Match against program errors
    if (err.error.errorCode.code === "InsufficientFunds") {
      // Handle specific error
    }
  } else if (err instanceof anchor.web3.SendTransactionError) {
    console.log("Transaction failed:", err.logs);
  } else {
    throw err;
  }
}
```

Anchor wraps program errors in `AnchorError` with typed error codes matching your `#[error_code]` enum. Access `.error.errorCode.code` for the string name."""),

    ("subscribe to account changes via WebSocket",
     """```typescript
const subscriptionId = program.account.gameState.subscribe(
  accountPubkey,
  "confirmed"
);

program.account.gameState.subscribe(accountPubkey).on("change", (account) => {
  console.log("Score updated:", account.score.toNumber());
  console.log("Level:", account.level);
});

// Alternative: low-level subscription
const wsId = provider.connection.onAccountChange(
  accountPubkey,
  (accountInfo) => {
    const decoded = program.coder.accounts.decode("gameState", accountInfo.data);
    console.log("Decoded:", decoded);
  },
  "confirmed"
);

// Cleanup
provider.connection.removeAccountChangeListener(wsId);
```

Anchor's `.subscribe()` auto-deserializes. For raw subscriptions, use `program.coder.accounts.decode()` with the account name."""),

    ("build a transaction with multiple instructions",
     """```typescript
const tx = new anchor.web3.Transaction();

// Add compute budget
tx.add(ComputeBudgetProgram.setComputeUnitLimit({ units: 400_000 }));

// Add multiple program instructions
const ix1 = await program.methods
  .deposit(new anchor.BN(1_000_000))
  .accounts({ /* ... */ })
  .instruction();

const ix2 = await program.methods
  .stake(new anchor.BN(1_000_000))
  .accounts({ /* ... */ })
  .instruction();

tx.add(ix1, ix2);

const sig = await provider.sendAndConfirm(tx);
```

Use `.instruction()` instead of `.rpc()` to get an `Instruction` object without sending. Bundle into a single atomic transaction."""),

    ("use versioned transactions with address lookup tables",
     """```typescript
import { AddressLookupTableProgram, TransactionMessage, VersionedTransaction } from "@solana/web3.js";

// Fetch ALT
const altAddress = new anchor.web3.PublicKey("ALT_ADDRESS_HERE");
const altAccount = await provider.connection.getAddressLookupTable(altAddress);
const alt = altAccount.value;

// Build versioned transaction
const ix = await program.methods.swap(new anchor.BN(amount))
  .accounts({ /* ... */ })
  .instruction();

const blockhash = await provider.connection.getLatestBlockhash();
const messageV0 = new TransactionMessage({
  payerKey: provider.wallet.publicKey,
  recentBlockhash: blockhash.blockhash,
  instructions: [ix],
}).compileToV0Message([alt]);

const tx = new VersionedTransaction(messageV0);
const signed = await provider.wallet.signTransaction(tx);
const sig = await provider.connection.sendRawTransaction(signed.serialize());
```

Versioned transactions with ALTs reduce transaction size by referencing accounts via indexes instead of full 32-byte pubkeys."""),

    ("simulate a transaction before sending",
     """```typescript
// Method 1: Anchor's simulate
const result = await program.methods
  .complexOperation(new anchor.BN(amount))
  .accounts({ /* ... */ })
  .simulate();

console.log("Return value:", result.returnValue);
console.log("Compute units:", result.raw.value.unitsConsumed);
console.log("Logs:", result.raw.value.logs);

// Method 2: Low-level simulate
const tx = await program.methods
  .complexOperation(new anchor.BN(amount))
  .accounts({ /* ... */ })
  .transaction();

tx.recentBlockhash = (await provider.connection.getLatestBlockhash()).blockhash;
tx.feePayer = provider.wallet.publicKey;

const simResult = await provider.connection.simulateTransaction(tx);
if (simResult.value.err) {
  console.error("Simulation failed:", simResult.value.err);
  console.error("Logs:", simResult.value.logs);
}
```

Always simulate before sending expensive or irreversible operations. Check `unitsConsumed` to set an appropriate compute budget."""),

    ("create and use a Keypair wallet for testing",
     """```typescript
import { Keypair, LAMPORTS_PER_SOL } from "@solana/web3.js";

// Generate a new keypair
const user = Keypair.generate();

// Airdrop SOL for testing (devnet/localnet only)
const sig = await provider.connection.requestAirdrop(
  user.publicKey,
  2 * LAMPORTS_PER_SOL
);
await provider.connection.confirmTransaction(sig);

// Use as signer in transaction
const tx = await program.methods
  .createProfile("Alice")
  .accounts({
    user: user.publicKey,
    userProfile: profilePda,
    systemProgram: anchor.web3.SystemProgram.programId,
  })
  .signers([user])
  .rpc();
```

Use `.signers([keypair])` to add additional signers beyond the wallet. The provider's wallet is always an implicit signer."""),

    ("use getProgramAccounts with complex filters",
     """```typescript
// Filter accounts by discriminator + specific field values
const accounts = await provider.connection.getProgramAccounts(
  program.programId,
  {
    filters: [
      { dataSize: 8 + 32 + 32 + 8 + 1 }, // exact account size
      {
        memcmp: {
          offset: 8, // skip 8-byte discriminator
          bytes: sellerPubkey.toBase58(), // seller field at offset 8
        },
      },
      {
        memcmp: {
          offset: 8 + 32 + 32 + 8, // offset to is_active field
          bytes: anchor.utils.bytes.bs58.encode(Buffer.from([1])), // true
        },
      },
    ],
  }
);

// Decode each account
const decoded = accounts.map(({ pubkey, account }) => ({
  pubkey,
  data: program.coder.accounts.decode("listing", account.data),
}));
```

Calculate offsets manually: 8-byte discriminator + cumulative field sizes. Use `memcmp` for exact byte matching at specific offsets."""),

    ("confirm transactions with different commitment levels",
     """```typescript
// Send with explicit confirmation
const sig = await program.methods
  .initialize()
  .accounts({ /* ... */ })
  .rpc({ commitment: "confirmed" });

// Wait for finalization separately
const latestBlockhash = await provider.connection.getLatestBlockhash();
const confirmation = await provider.connection.confirmTransaction(
  {
    signature: sig,
    blockhash: latestBlockhash.blockhash,
    lastValidBlockHeight: latestBlockhash.lastValidBlockHeight,
  },
  "finalized"
);

if (confirmation.value.err) {
  throw new Error(`Transaction failed: ${confirmation.value.err}`);
}
```

Commitment levels: `processed` (fastest, may be rolled back), `confirmed` (voted on by supermajority), `finalized` (31+ confirmations, irreversible). Use `confirmed` for most operations, `finalized` for critical ones."""),
]

for desc, code in TS_PATTERNS:
    q = f"How do I {desc} in a Solana TypeScript client?"
    a = code
    PAIRS.append(("typescript-client", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Testing Patterns (Anchor + Bankrun)
# ═══════════════════════════════════════════════════════════════════════════════

TEST_PATTERNS = [
    ("basic Anchor test setup",
     """```typescript
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { expect } from "chai";
import { MyProgram } from "../target/types/my_program";

describe("my_program", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.MyProgram as Program<MyProgram>;

  it("initializes correctly", async () => {
    const [pda] = anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from("config")],
      program.programId
    );

    await program.methods
      .initialize()
      .accounts({
        config: pda,
        admin: provider.wallet.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc();

    const account = await program.account.config.fetch(pda);
    expect(account.admin.toBase58()).to.equal(
      provider.wallet.publicKey.toBase58()
    );
  });
});
```"""),

    ("test that an instruction fails with expected error",
     """```typescript
it("rejects unauthorized access", async () => {
  const unauthorized = anchor.web3.Keypair.generate();

  // Airdrop for fees
  const sig = await provider.connection.requestAirdrop(
    unauthorized.publicKey,
    anchor.web3.LAMPORTS_PER_SOL
  );
  await provider.connection.confirmTransaction(sig);

  try {
    await program.methods
      .adminOnly()
      .accounts({
        config: configPda,
        admin: unauthorized.publicKey,
      })
      .signers([unauthorized])
      .rpc();
    expect.fail("Should have thrown");
  } catch (err) {
    expect(err).to.be.instanceOf(anchor.AnchorError);
    expect(err.error.errorCode.code).to.equal("Unauthorized");
  }
});
```

Always test error paths. Use `expect.fail()` to catch cases where the transaction succeeds unexpectedly."""),

    ("test with multiple users",
     """```typescript
describe("multi-user scenario", () => {
  const alice = anchor.web3.Keypair.generate();
  const bob = anchor.web3.Keypair.generate();

  before(async () => {
    // Fund both users
    for (const user of [alice, bob]) {
      const sig = await provider.connection.requestAirdrop(
        user.publicKey,
        2 * anchor.web3.LAMPORTS_PER_SOL
      );
      await provider.connection.confirmTransaction(sig);
    }

    // Initialize accounts for both
    for (const user of [alice, bob]) {
      const [pda] = anchor.web3.PublicKey.findProgramAddressSync(
        [Buffer.from("profile"), user.publicKey.toBuffer()],
        program.programId
      );
      await program.methods
        .createProfile("User")
        .accounts({ profile: pda, user: user.publicKey })
        .signers([user])
        .rpc();
    }
  });

  it("alice transfers to bob", async () => {
    // ... test interaction between users
  });
});
```"""),

    ("test token operations",
     """```typescript
import { createMint, createAccount, mintTo, getAccount } from "@solana/spl-token";

it("deposits tokens into vault", async () => {
  // Create mint
  const mint = await createMint(
    provider.connection,
    (provider.wallet as anchor.Wallet).payer,
    provider.wallet.publicKey,
    null,
    6
  );

  // Create user token account and mint tokens
  const userAta = await createAccount(
    provider.connection,
    (provider.wallet as anchor.Wallet).payer,
    mint,
    provider.wallet.publicKey
  );
  await mintTo(
    provider.connection,
    (provider.wallet as anchor.Wallet).payer,
    mint,
    userAta,
    provider.wallet.publicKey,
    1_000_000
  );

  // Deposit into program vault
  const [vaultPda] = anchor.web3.PublicKey.findProgramAddressSync(
    [Buffer.from("vault"), mint.toBuffer()],
    program.programId
  );

  await program.methods
    .deposit(new anchor.BN(500_000))
    .accounts({ mint, userToken: userAta, vault: vaultPda })
    .rpc();

  // Verify
  const vaultAccount = await getAccount(provider.connection, vaultPda);
  expect(Number(vaultAccount.amount)).to.equal(500_000);
});
```"""),

    ("test with bankrun for fast local testing",
     """```typescript
import { startAnchor } from "solana-bankrun";
import { BankrunProvider } from "anchor-bankrun";
import { Program } from "@coral-xyz/anchor";

describe("bankrun tests", () => {
  let provider: BankrunProvider;
  let program: Program<MyProgram>;

  before(async () => {
    const context = await startAnchor(".", [], []);
    provider = new BankrunProvider(context);
    program = new Program(IDL, provider);
  });

  it("runs fast without validator", async () => {
    await program.methods.initialize().accounts({ /* ... */ }).rpc();
    // Bankrun tests run 10-100x faster than anchor test
  });

  it("can warp time", async () => {
    const currentClock = await context.banksClient.getClock();
    context.setClock({
      ...currentClock,
      unixTimestamp: BigInt(currentClock.unixTimestamp) + BigInt(86400),
    });
    // Now the clock is 1 day in the future
    await program.methods.checkExpiry().accounts({ /* ... */ }).rpc();
  });
});
```

Bankrun runs a lightweight BPF VM in-process — no validator needed. Supports time warping, account injection, and is much faster for CI."""),

    ("test account state changes comprehensively",
     """```typescript
it("tracks state transitions correctly", async () => {
  // Create
  await program.methods.createOrder(new anchor.BN(1000)).accounts({ /* ... */ }).rpc();
  let order = await program.account.order.fetch(orderPda);
  expect(Object.keys(order.state)[0]).to.equal("created");
  expect(order.amount.toNumber()).to.equal(1000);

  // Fund
  await program.methods.fundOrder().accounts({ /* ... */ }).rpc();
  order = await program.account.order.fetch(orderPda);
  expect(Object.keys(order.state)[0]).to.equal("funded");

  // Complete
  await program.methods.settleOrder().accounts({ /* ... */ }).rpc();
  order = await program.account.order.fetch(orderPda);
  expect(Object.keys(order.state)[0]).to.equal("settled");
  expect(order.settledAt.toNumber()).to.be.greaterThan(0);
});
```

Anchor serializes enums as objects with a single key. Check state with `Object.keys(account.state)[0]`."""),
]

for desc, code in TEST_PATTERNS:
    q = f"Show me how to write a {desc} for a Solana Anchor program."
    a = code
    PAIRS.append(("testing", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# DeFi Protocol Patterns
# ═══════════════════════════════════════════════════════════════════════════════

DEFI_PATTERNS = [
    ("constant product AMM swap", """Implement a constant product AMM (x * y = k) swap:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Transfer, Token, TokenAccount, Mint};

#[program]
pub mod amm {
    use super::*;

    pub fn swap(ctx: Context<Swap>, amount_in: u64, minimum_amount_out: u64) -> Result<()> {
        let pool = &mut ctx.accounts.pool;

        let reserve_in = ctx.accounts.pool_token_in.amount;
        let reserve_out = ctx.accounts.pool_token_out.amount;

        // Constant product: (reserve_in + amount_in) * (reserve_out - amount_out) = k
        // amount_out = reserve_out - k / (reserve_in + amount_in)
        let k = (reserve_in as u128).checked_mul(reserve_out as u128)
            .ok_or(AmmError::MathOverflow)?;

        let new_reserve_in = (reserve_in as u128).checked_add(amount_in as u128)
            .ok_or(AmmError::MathOverflow)?;

        let new_reserve_out = k.checked_div(new_reserve_in)
            .ok_or(AmmError::MathOverflow)?;

        let amount_out = (reserve_out as u128).checked_sub(new_reserve_out)
            .ok_or(AmmError::MathOverflow)? as u64;

        // Apply fee (30 bps)
        let fee = amount_out.checked_mul(30).ok_or(AmmError::MathOverflow)?
            .checked_div(10_000).ok_or(AmmError::MathOverflow)?;
        let amount_out_after_fee = amount_out.checked_sub(fee)
            .ok_or(AmmError::MathOverflow)?;

        require!(amount_out_after_fee >= minimum_amount_out, AmmError::SlippageExceeded);

        // Transfer tokens in
        token::transfer(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), Transfer {
                from: ctx.accounts.user_token_in.to_account_info(),
                to: ctx.accounts.pool_token_in.to_account_info(),
                authority: ctx.accounts.user.to_account_info(),
            }),
            amount_in,
        )?;

        // Transfer tokens out (PDA-signed)
        let seeds = &[b"pool".as_ref(), &[pool.bump]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.pool_token_out.to_account_info(),
                    to: ctx.accounts.user_token_out.to_account_info(),
                    authority: pool.to_account_info(),
                },
                &[seeds],
            ),
            amount_out_after_fee,
        )?;

        emit!(SwapEvent {
            user: ctx.accounts.user.key(),
            amount_in,
            amount_out: amount_out_after_fee,
        });

        Ok(())
    }
}

#[error_code]
pub enum AmmError {
    #[msg("Math overflow")]
    MathOverflow,
    #[msg("Slippage tolerance exceeded")]
    SlippageExceeded,
}
```

Key safety features:
- Checked arithmetic throughout (no overflow)
- Slippage protection via `minimum_amount_out`
- Fee applied before output (not on input)
- PDA-signed transfer for pool outflow"""),

    ("staking with time-based rewards", """Implement a staking program with rewards proportional to time staked:

```rust
use anchor_lang::prelude::*;

#[program]
pub mod staking {
    use super::*;

    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let user_stake = &mut ctx.accounts.user_stake;
        let clock = Clock::get()?;

        // Claim any pending rewards first
        if user_stake.amount > 0 {
            let pending = calculate_pending(user_stake, pool, clock.unix_timestamp)?;
            if pending > 0 {
                // Transfer pending rewards...
                user_stake.rewards_claimed = user_stake.rewards_claimed
                    .checked_add(pending).ok_or(StakeError::MathOverflow)?;
            }
        }

        // Update state
        user_stake.amount = user_stake.amount.checked_add(amount)
            .ok_or(StakeError::MathOverflow)?;
        user_stake.last_claim_time = clock.unix_timestamp;
        pool.total_staked = pool.total_staked.checked_add(amount)
            .ok_or(StakeError::MathOverflow)?;

        // Transfer tokens to pool via CPI...
        Ok(())
    }

    pub fn unstake(ctx: Context<Unstake>, amount: u64) -> Result<()> {
        let user_stake = &mut ctx.accounts.user_stake;
        require!(user_stake.amount >= amount, StakeError::InsufficientStake);
        require!(
            Clock::get()?.unix_timestamp >= user_stake.lockup_end,
            StakeError::LockupNotExpired
        );
        // Claim rewards + transfer tokens back...
        user_stake.amount = user_stake.amount.checked_sub(amount)
            .ok_or(StakeError::MathOverflow)?;
        Ok(())
    }
}

fn calculate_pending(
    user_stake: &UserStake,
    pool: &StakingPool,
    current_time: i64,
) -> Result<u64> {
    let elapsed = current_time.checked_sub(user_stake.last_claim_time)
        .ok_or(StakeError::MathOverflow)?;
    if elapsed <= 0 || pool.total_staked == 0 {
        return Ok(0);
    }
    let reward = (user_stake.amount as u128)
        .checked_mul(pool.reward_rate as u128).ok_or(StakeError::MathOverflow)?
        .checked_mul(elapsed as u128).ok_or(StakeError::MathOverflow)?
        .checked_div(pool.total_staked as u128).ok_or(StakeError::MathOverflow)?;
    Ok(reward as u64)
}

#[account]
#[derive(InitSpace)]
pub struct StakingPool {
    pub authority: Pubkey,
    pub reward_mint: Pubkey,
    pub total_staked: u64,
    pub reward_rate: u64, // rewards per second per total stake
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct UserStake {
    pub owner: Pubkey,
    pub amount: u64,
    pub last_claim_time: i64,
    pub lockup_end: i64,
    pub rewards_claimed: u64,
    pub bump: u8,
}
```"""),

    ("token vesting with cliff and linear release", """Implement a vesting schedule with cliff and linear vesting:

```rust
use anchor_lang::prelude::*;

#[program]
pub mod vesting {
    use super::*;

    pub fn create_vesting(
        ctx: Context<CreateVesting>,
        total_amount: u64,
        start_time: i64,
        cliff_duration: i64,
        total_duration: i64,
    ) -> Result<()> {
        require!(total_duration > cliff_duration, VestingError::InvalidSchedule);
        require!(total_amount > 0, VestingError::ZeroAmount);

        let schedule = &mut ctx.accounts.vesting_schedule;
        schedule.beneficiary = ctx.accounts.beneficiary.key();
        schedule.mint = ctx.accounts.mint.key();
        schedule.total_amount = total_amount;
        schedule.claimed_amount = 0;
        schedule.start_time = start_time;
        schedule.cliff_time = start_time.checked_add(cliff_duration)
            .ok_or(VestingError::MathOverflow)?;
        schedule.end_time = start_time.checked_add(total_duration)
            .ok_or(VestingError::MathOverflow)?;
        schedule.bump = ctx.bumps.vesting_schedule;

        // Transfer tokens to vesting vault via CPI...
        Ok(())
    }

    pub fn claim(ctx: Context<Claim>) -> Result<()> {
        let schedule = &mut ctx.accounts.vesting_schedule;
        let clock = Clock::get()?;

        let vested = calculate_vested(schedule, clock.unix_timestamp)?;
        let claimable = vested.checked_sub(schedule.claimed_amount)
            .ok_or(VestingError::MathOverflow)?;

        require!(claimable > 0, VestingError::NothingToClaim);

        schedule.claimed_amount = schedule.claimed_amount
            .checked_add(claimable).ok_or(VestingError::MathOverflow)?;

        // Transfer claimable tokens from vault to beneficiary via PDA CPI...
        Ok(())
    }
}

fn calculate_vested(schedule: &VestingSchedule, now: i64) -> Result<u64> {
    if now < schedule.cliff_time {
        return Ok(0); // Before cliff: nothing vested
    }
    if now >= schedule.end_time {
        return Ok(schedule.total_amount); // After end: everything vested
    }
    // Linear vesting between cliff and end
    let elapsed = (now - schedule.start_time) as u128;
    let duration = (schedule.end_time - schedule.start_time) as u128;
    let vested = (schedule.total_amount as u128)
        .checked_mul(elapsed).ok_or(VestingError::MathOverflow)?
        .checked_div(duration).ok_or(VestingError::MathOverflow)?;
    Ok(vested as u64)
}

#[account]
#[derive(InitSpace)]
pub struct VestingSchedule {
    pub beneficiary: Pubkey,
    pub mint: Pubkey,
    pub total_amount: u64,
    pub claimed_amount: u64,
    pub start_time: i64,
    pub cliff_time: i64,
    pub end_time: i64,
    pub bump: u8,
}
```

The cliff period means nothing vests until `cliff_time`. After that, tokens vest linearly until `end_time`."""),

    ("lending with collateral ratio checks", """Implement a basic lending protocol with collateral validation:

```rust
use anchor_lang::prelude::*;

const MIN_COLLATERAL_RATIO: u64 = 150; // 150%
const LIQUIDATION_THRESHOLD: u64 = 120; // 120%
const PRECISION: u64 = 100;

#[program]
pub mod lending {
    use super::*;

    pub fn borrow(ctx: Context<Borrow>, borrow_amount: u64) -> Result<()> {
        let position = &mut ctx.accounts.position;
        let pool = &ctx.accounts.lending_pool;

        // Calculate collateral ratio after borrow
        let new_borrow = position.borrowed.checked_add(borrow_amount)
            .ok_or(LendingError::MathOverflow)?;

        let collateral_value = get_collateral_value(
            position.collateral_amount,
            pool.collateral_price,
        )?;
        let borrow_value = get_borrow_value(new_borrow, pool.borrow_price)?;

        let ratio = collateral_value.checked_mul(PRECISION)
            .ok_or(LendingError::MathOverflow)?
            .checked_div(borrow_value)
            .ok_or(LendingError::MathOverflow)?;

        require!(ratio >= MIN_COLLATERAL_RATIO, LendingError::InsufficientCollateral);
        require!(
            new_borrow <= pool.available_liquidity(),
            LendingError::InsufficientLiquidity
        );

        position.borrowed = new_borrow;
        // Transfer borrowed tokens to user via PDA CPI...
        Ok(())
    }

    pub fn liquidate(ctx: Context<Liquidate>, repay_amount: u64) -> Result<()> {
        let position = &ctx.accounts.position;
        let pool = &ctx.accounts.lending_pool;

        // Check position is liquidatable
        let ratio = calculate_ratio(position, pool)?;
        require!(ratio < LIQUIDATION_THRESHOLD, LendingError::NotLiquidatable);

        // Liquidation bonus: 5%
        let collateral_to_seize = repay_amount
            .checked_mul(105).ok_or(LendingError::MathOverflow)?
            .checked_div(100).ok_or(LendingError::MathOverflow)?;

        // Transfer repay_amount from liquidator, seize collateral...
        Ok(())
    }
}
```

Key design:
- Collateral ratio checked BEFORE every borrow
- Liquidation only allowed when ratio drops below threshold
- 5% liquidation bonus incentivizes liquidators
- All math uses checked operations with u128 intermediates"""),

    ("escrow with timeout and refund", """Implement an escrow that automatically allows refunds after expiry:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Transfer, Token, TokenAccount};

#[program]
pub mod escrow {
    use super::*;

    pub fn create_escrow(
        ctx: Context<CreateEscrow>,
        amount: u64,
        expiry_seconds: i64,
    ) -> Result<()> {
        let clock = Clock::get()?;
        let escrow = &mut ctx.accounts.escrow;
        escrow.maker = ctx.accounts.maker.key();
        escrow.mint = ctx.accounts.mint.key();
        escrow.amount = amount;
        escrow.expiry = clock.unix_timestamp.checked_add(expiry_seconds)
            .ok_or(EscrowError::MathOverflow)?;
        escrow.is_completed = false;
        escrow.bump = ctx.bumps.escrow;

        // Transfer tokens to escrow vault
        token::transfer(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), Transfer {
                from: ctx.accounts.maker_token.to_account_info(),
                to: ctx.accounts.vault.to_account_info(),
                authority: ctx.accounts.maker.to_account_info(),
            }),
            amount,
        )?;
        Ok(())
    }

    pub fn complete_escrow(ctx: Context<CompleteEscrow>) -> Result<()> {
        let escrow = &mut ctx.accounts.escrow;
        require!(!escrow.is_completed, EscrowError::AlreadyCompleted);
        require!(
            Clock::get()?.unix_timestamp <= escrow.expiry,
            EscrowError::Expired
        );

        escrow.is_completed = true;
        // Transfer from vault to taker via PDA CPI...
        Ok(())
    }

    pub fn refund_escrow(ctx: Context<RefundEscrow>) -> Result<()> {
        let escrow = &ctx.accounts.escrow;
        require!(!escrow.is_completed, EscrowError::AlreadyCompleted);
        require!(
            Clock::get()?.unix_timestamp > escrow.expiry,
            EscrowError::NotExpired
        );

        // Transfer from vault back to maker via PDA CPI...
        Ok(())
    }
}
```

Safety: The maker can only refund after expiry. The taker can only claim before expiry. Once completed, no further actions are possible."""),

    ("flash loan implementation", """Implement a flash loan pattern on Solana:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Transfer, Token, TokenAccount};

#[program]
pub mod flash_loan {
    use super::*;

    pub fn borrow_flash(ctx: Context<BorrowFlash>, amount: u64) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        let fee = amount.checked_mul(pool.fee_bps as u64)
            .ok_or(FlashError::MathOverflow)?
            .checked_div(10_000)
            .ok_or(FlashError::MathOverflow)?;

        // Record pre-loan balance
        pool.expected_repayment = amount.checked_add(fee)
            .ok_or(FlashError::MathOverflow)?;
        pool.flash_loan_active = true;

        // Transfer tokens to borrower
        let seeds = &[b"pool".as_ref(), &[pool.bump]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.pool_vault.to_account_info(),
                    to: ctx.accounts.borrower_token.to_account_info(),
                    authority: pool.to_account_info(),
                },
                &[seeds],
            ),
            amount,
        )?;
        Ok(())
    }

    pub fn repay_flash(ctx: Context<RepayFlash>) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        require!(pool.flash_loan_active, FlashError::NoActiveLoan);

        // Verify repayment
        let vault_balance = ctx.accounts.pool_vault.amount;
        require!(
            vault_balance >= pool.pre_loan_balance
                .checked_add(pool.expected_repayment)
                .ok_or(FlashError::MathOverflow)?,
            FlashError::InsufficientRepayment
        );

        pool.flash_loan_active = false;
        pool.expected_repayment = 0;
        Ok(())
    }
}
```

Note: On Solana, flash loans work across two instructions in the same transaction (borrow → use → repay). The `flash_loan_active` flag ensures repayment happens within the same transaction since the state reverts on failure."""),
]

for title, code in DEFI_PATTERNS:
    q = f"How do I implement a {title.split(' ', 1)[0] if title[0].islower() else title.lower()} in Anchor?"
    a = code
    PAIRS.append(("defi", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Security Patterns
# ═══════════════════════════════════════════════════════════════════════════════

SECURITY_PATTERNS = [
    ("type cosplay prevention",
     "How do I prevent type cosplay attacks in Anchor?",
     """Anchor's `Account<'info, T>` type automatically checks the 8-byte discriminator, preventing type cosplay. Here's what happens under the hood:

```rust
// Anchor automatically adds an 8-byte discriminator to every #[account]
#[account]
pub struct Vault {
    pub authority: Pubkey,
    pub balance: u64,
}

// This discriminator is SHA-256("account:Vault")[..8]
// When you use Account<'info, Vault>, Anchor checks this discriminator

// SAFE: Anchor validates the discriminator
#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut, has_one = authority)]
    pub vault: Account<'info, Vault>,  // ✅ Type-checked
    pub authority: Signer<'info>,
}

// UNSAFE: Using UncheckedAccount bypasses type checking
#[derive(Accounts)]
pub struct UnsafeWithdraw<'info> {
    /// CHECK: DANGEROUS — no type validation!
    #[account(mut)]
    pub vault: UncheckedAccount<'info>,  // ❌ Any account could be passed
    pub authority: Signer<'info>,
}
```

Rules:
1. Always use `Account<'info, T>` for program-owned accounts — never `UncheckedAccount`
2. If you must use `UncheckedAccount`, manually verify the discriminator
3. `/// CHECK:` comments are required by Anchor for unchecked accounts — they force you to document why it's safe
4. Cross-program accounts should use `Program<'info, T>` or `Account` with owner checks"""),

    ("signer verification",
     "What are the best practices for signer verification in Anchor?",
     """Always verify signers explicitly. Anchor's `Signer<'info>` type ensures the account signed the transaction:

```rust
#[derive(Accounts)]
pub struct SecureAction<'info> {
    // ✅ Signer is verified by Anchor at deserialization time
    pub authority: Signer<'info>,

    // ✅ has_one links the PDA to the signer
    #[account(
        mut,
        has_one = authority,
        seeds = [b"vault", authority.key().as_ref()],
        bump = vault.bump,
    )]
    pub vault: Account<'info, Vault>,
}

// ❌ WRONG: Missing signer check
#[derive(Accounts)]
pub struct InsecureAction<'info> {
    /// CHECK: WRONG — no signer verification!
    pub authority: UncheckedAccount<'info>,
    #[account(mut)]
    pub vault: Account<'info, Vault>,
}
```

Signer verification checklist:
1. Use `Signer<'info>` for all authority/admin/owner accounts
2. Use `has_one` to link the signer to stored authority fields
3. For multi-step operations, verify the signer at EACH step
4. For PDAs that act as authorities, use `CpiContext::new_with_signer`
5. Never use `UncheckedAccount` for accounts that should be signers"""),

    ("arithmetic overflow prevention",
     "How do I prevent arithmetic overflow in Solana programs?",
     """Solana programs compile with overflow checks DISABLED (`overflow-checks = false` in release). Always use checked math:

```rust
// ❌ UNSAFE: Silent overflow in release builds
let result = a * b + c;

// ✅ SAFE: Explicit overflow handling
let result = a.checked_mul(b)
    .ok_or(MyError::MathOverflow)?
    .checked_add(c)
    .ok_or(MyError::MathOverflow)?;

// ✅ SAFE: Use u128 for intermediate calculations
let fee = (amount as u128)
    .checked_mul(fee_bps as u128)
    .ok_or(MyError::MathOverflow)?
    .checked_div(10_000)
    .ok_or(MyError::MathOverflow)? as u64;

// ✅ SAFE: Saturating arithmetic when overflow should clamp
let capped = balance.saturating_add(reward); // caps at u64::MAX

// ✅ Enable overflow checks in Cargo.toml for extra safety:
// [profile.release]
// overflow-checks = true
```

Common pitfalls:
- `u64 * u64` can exceed u64::MAX — upcast to u128
- Subtraction underflow: always check `a >= b` before `a - b`
- Division by zero: check divisor > 0
- Timestamp arithmetic: i64 can overflow with large durations"""),

    ("account ownership verification",
     "How do I verify account ownership in Anchor?",
     """Anchor provides multiple layers of ownership verification:

```rust
// 1. Program-owned accounts: automatically checked via Account<'info, T>
#[derive(Accounts)]
pub struct Safe<'info> {
    // ✅ Anchor verifies this account is owned by YOUR program
    #[account(mut)]
    pub my_data: Account<'info, MyData>,

    // ✅ Anchor verifies this is owned by the Token program
    #[account(mut)]
    pub token_account: Account<'info, TokenAccount>,

    // ✅ Anchor verifies this is the System Program
    pub system_program: Program<'info, System>,
}

// 2. Explicit owner check for raw accounts
#[derive(Accounts)]
pub struct WithOwnerCheck<'info> {
    /// CHECK: Validated by owner constraint
    #[account(
        owner = token::ID @ MyError::WrongOwner,
    )]
    pub external_token: UncheckedAccount<'info>,
}

// 3. Token account owner (the wallet, not program owner)
#[derive(Accounts)]
pub struct TokenOwnerCheck<'info> {
    #[account(
        mut,
        constraint = user_token.owner == user.key() @ MyError::WrongTokenOwner,
    )]
    pub user_token: Account<'info, TokenAccount>,
    pub user: Signer<'info>,
}
```

Key distinction:
- **Account owner** (`.owner`): The program that owns the account data (system, token, your program)
- **Token account owner** (`.owner` field in TokenAccount): The wallet that controls the token account
- Both must be verified for token operations"""),

    ("rent exemption and account closing",
     "How do I safely handle rent and account closing in Anchor?",
     """```rust
// Anchor handles rent-exemption automatically for init
#[derive(Accounts)]
pub struct Create<'info> {
    #[account(
        init,
        payer = payer,
        space = 8 + MyAccount::INIT_SPACE,
        // Anchor calculates rent and charges payer automatically
    )]
    pub my_account: Account<'info, MyAccount>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
}

// Safe closing with close constraint
#[derive(Accounts)]
pub struct Close<'info> {
    #[account(
        mut,
        close = receiver,  // Transfers ALL lamports to receiver
        has_one = authority,
    )]
    pub my_account: Account<'info, MyAccount>,
    #[account(mut)]
    pub receiver: SystemAccount<'info>,
    pub authority: Signer<'info>,
}
```

The `close` constraint:
1. Transfers all lamports from the account to the receiver
2. Zeroes out all account data (prevents resurrection attacks)
3. Assigns the account to the system program
4. This is done AFTER the instruction handler runs

**Resurrection attack prevention:** After closing, the account's data is zeroed and owner changed. If someone re-creates the account at the same address, Anchor's discriminator check prevents it from being deserialized as the old type (the 8-byte discriminator won't match)."""),

    ("input validation patterns",
     "What input validation should I add to my Anchor program?",
     """Validate all external inputs at the boundary:

```rust
#[program]
pub mod validated {
    use super::*;

    pub fn create_pool(
        ctx: Context<CreatePool>,
        fee_bps: u16,
        min_deposit: u64,
        name: String,
    ) -> Result<()> {
        // Validate numeric ranges
        require!(fee_bps <= 10_000, MyError::FeeTooHigh);
        require!(min_deposit > 0, MyError::InvalidAmount);

        // Validate string inputs
        require!(name.len() <= 32, MyError::NameTooLong);
        require!(!name.is_empty(), MyError::NameEmpty);
        require!(
            name.chars().all(|c| c.is_alphanumeric() || c == '_' || c == '-'),
            MyError::InvalidCharacters
        );

        // Validate pubkey inputs
        require!(
            ctx.accounts.oracle.key() != Pubkey::default(),
            MyError::InvalidOracle
        );

        // Validate timestamps
        let clock = Clock::get()?;
        require!(
            ctx.accounts.pool.end_time > clock.unix_timestamp,
            MyError::InvalidEndTime
        );

        Ok(())
    }
}

// Account-level validation via constraints
#[derive(Accounts)]
#[instruction(fee_bps: u16)]
pub struct CreatePool<'info> {
    #[account(
        init,
        payer = admin,
        space = 8 + Pool::INIT_SPACE,
        constraint = fee_bps <= 10_000 @ MyError::FeeTooHigh,
    )]
    pub pool: Account<'info, Pool>,
    pub admin: Signer<'info>,
    /// CHECK: Oracle account validated in instruction
    pub oracle: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}
```

Validate at BOTH levels:
- **Account constraints**: Check account relationships, ownership, PDA derivation
- **Instruction handler**: Check numeric ranges, string formats, business logic"""),
]

for title, question, answer in SECURITY_PATTERNS:
    PAIRS.append(("security", m(question, answer)))


# ═══════════════════════════════════════════════════════════════════════════════
# Solana Concepts (explanatory)
# ═══════════════════════════════════════════════════════════════════════════════

CONCEPTS = [
    ("How does Solana's account model differ from Ethereum's?",
     """Solana uses an **account model** that's fundamentally different from Ethereum:

**Solana:**
- Programs (smart contracts) are **stateless** — they don't store data
- Data lives in separate **accounts** that programs own
- Programs can only modify accounts they own
- Accounts must be passed explicitly to every instruction
- Accounts pay **rent** (or are rent-exempt with sufficient lamports)
- Account size is fixed at creation (unless `realloc` is used)

**Ethereum:**
- Smart contracts store their own state in storage slots
- State is implicit — contracts access their own storage
- No concept of "passing accounts"
- Storage costs gas but no ongoing rent

**Practical implications for Solana:**
```
Program (code) ──owns──→ Account A (data for user 1)
                ──owns──→ Account B (data for user 2)
                ──owns──→ Account C (global config)
```

Every transaction must specify ALL accounts it will read or write. This enables Solana's parallel transaction execution — the runtime can run transactions in parallel if they don't touch the same accounts.

**Account anatomy:**
- `lamports`: SOL balance
- `data`: Byte array (your program's data)
- `owner`: Program that can modify the data
- `executable`: Whether this account is a program
- `rent_epoch`: When rent was last collected"""),

    ("What are compute units (CU) and how do I optimize for them?",
     """Compute Units (CU) are Solana's execution cost measure, similar to Ethereum's gas:

**Defaults:**
- Max per instruction: 200,000 CU
- Max per transaction: 1,400,000 CU (1.4M)
- Can request up to 1,400,000 CU per transaction

**Common costs:**
- Account deserialization: ~1,000-5,000 CU per account
- PDA derivation: ~1,500 CU
- SHA-256 (32 bytes): ~100 CU
- CPI call overhead: ~1,000-2,000 CU
- Log message: ~100 CU per `msg!`
- Syscall: varies, ~100-1,000 CU

**Optimization strategies:**

```rust
// 1. Store PDA bumps to avoid re-derivation (saves ~4,500 CU)
#[account(
    seeds = [b"vault", authority.key().as_ref()],
    bump = vault.bump,  // stored bump vs. bump (runtime search)
)]

// 2. Use zero-copy for large accounts (avoids full deserialization)
#[account(zero_copy)]
pub struct BigData { /* ... */ }

// 3. Minimize logging in production
#[cfg(feature = "verbose")]
msg!("Debug info: {}", value);

// 4. Batch operations to amortize CPI overhead
// Instead of 10 separate token transfers, design around fewer CPIs

// 5. Set appropriate CU limits
ComputeBudgetProgram.setComputeUnitLimit({ units: 300_000 })
```

**Priority fees** (in micro-lamports per CU) determine transaction priority. Higher CU price = faster inclusion during congestion."""),

    ("How do Solana transactions work?",
     """A Solana transaction consists of:

**Structure:**
```
Transaction
├── Signatures (1-12 signatures)
├── Message
│   ├── Header (num signers, read-only accounts)
│   ├── Account keys (all accounts referenced)
│   ├── Recent blockhash (for expiry)
│   └── Instructions (1 or more)
│       ├── Program ID index
│       ├── Account indexes
│       └── Instruction data (serialized args)
```

**Key properties:**
1. **Atomic**: All instructions succeed or all fail (no partial execution)
2. **Size limit**: 1,232 bytes (MTU minus headers)
3. **Expiry**: ~60-90 seconds (based on recent blockhash)
4. **Max accounts**: ~64 accounts per transaction (with ALTs: more)
5. **Max instructions**: Limited by size, typically 5-10

**Transaction lifecycle:**
```
Client → RPC Node → Leader Validator → Execute → Confirm
  │                                        │
  └── Signs with wallet                    └── All-or-nothing
```

**Versioned transactions** (v0) support Address Lookup Tables:
```typescript
// Legacy transaction: each account = 32 bytes
// Versioned + ALT: each account = 1 byte index

const messageV0 = new TransactionMessage({
  payerKey: wallet.publicKey,
  recentBlockhash: blockhash,
  instructions: [ix],
}).compileToV0Message([lookupTable]);
```

ALTs are essential for transactions that reference many accounts (DeFi swaps, batch operations)."""),

    ("What is the difference between processed, confirmed, and finalized commitment?",
     """Solana has three commitment levels for transaction confirmation:

**`processed`** (fastest, least certain):
- Transaction has been received and processed by the connected RPC node
- NOT voted on by any validators
- Can be rolled back (optimistic confirmation)
- Use for: UI updates, non-critical reads

**`confirmed`** (recommended default):
- Voted on by supermajority (2/3+) of stake-weighted validators
- Very unlikely to be rolled back (would require 1/3+ stake to be malicious)
- Use for: Most operations, account reads, after sending transactions

**`finalized`** (most certain, slowest):
- 31+ confirmed slots have passed (~12.4 seconds)
- Equivalent to Bitcoin's "6 confirmations"
- Cannot be rolled back under any circumstances
- Use for: High-value transfers, bridge operations, irreversible actions

```typescript
// Reading account data
const account = await connection.getAccountInfo(pubkey, "confirmed");

// Sending and confirming
const sig = await sendAndConfirmTransaction(
  connection,
  transaction,
  [signer],
  { commitment: "confirmed" }
);

// Waiting for finalization
await connection.confirmTransaction(sig, "finalized");
```

**Timing:**
- processed: ~400ms
- confirmed: ~400ms-1s
- finalized: ~12-15 seconds"""),

    ("How does Cross-Program Invocation (CPI) work?",
     """CPI allows one program to call another program's instructions:

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Transfer, Token, TokenAccount};

// Simple CPI: Call the Token program to transfer tokens
pub fn transfer_via_cpi(ctx: Context<TransferCpi>, amount: u64) -> Result<()> {
    let cpi_accounts = Transfer {
        from: ctx.accounts.source.to_account_info(),
        to: ctx.accounts.destination.to_account_info(),
        authority: ctx.accounts.authority.to_account_info(),
    };
    let cpi_ctx = CpiContext::new(
        ctx.accounts.token_program.to_account_info(),
        cpi_accounts,
    );
    token::transfer(cpi_ctx, amount)?;
    Ok(())
}

// PDA-signed CPI: The program's PDA acts as the signer
pub fn pda_signed_transfer(ctx: Context<PdaTransfer>, amount: u64) -> Result<()> {
    let seeds = &[
        b"vault".as_ref(),
        ctx.accounts.vault.authority.as_ref(),
        &[ctx.accounts.vault.bump],
    ];
    let signer_seeds = &[&seeds[..]];

    let cpi_ctx = CpiContext::new_with_signer(
        ctx.accounts.token_program.to_account_info(),
        Transfer { /* accounts */ },
        signer_seeds,
    );
    token::transfer(cpi_ctx, amount)?;
    Ok(())
}
```

**CPI rules:**
1. **Depth limit**: Max 4 levels deep (A → B → C → D)
2. **Privileges extend**: If A is a signer, A is still a signer in B's context
3. **Account ownership**: Only the owning program can modify account data
4. **PDA signing**: Programs can sign for their PDAs using seeds
5. **Compute budget**: Shared across the entire transaction

**Common CPI targets:**
- System Program: SOL transfers, account creation
- Token Program: SPL token operations
- Associated Token Program: ATA creation
- Other Anchor programs: Custom cross-program calls"""),

    ("What are Program Derived Addresses (PDAs) and why are they important?",
     """PDAs are deterministic addresses that only a program can sign for — they have no private key:

```
PDA = SHA-256(seeds, program_id, "ProgramDerivedAddress")
       ↓
If on ed25519 curve → bump down and retry
If OFF curve → valid PDA ✓
```

**Why PDAs matter:**
1. **Deterministic**: Same seeds always produce the same address
2. **Program authority**: Only the program can sign transactions for PDAs
3. **No private key**: Cannot be signed by any external wallet
4. **Unique addressing**: Seeds create namespaced, collision-free addresses

**Common PDA patterns:**

```rust
// 1. Per-user account (one per user per program)
seeds = [b"profile", user.key().as_ref()]

// 2. Pair/relationship account
seeds = [b"trade", maker.key().as_ref(), taker.key().as_ref()]

// 3. Indexed accounts
seeds = [b"order", user.key().as_ref(), &order_id.to_le_bytes()]

// 4. Singleton/global config
seeds = [b"config"]

// 5. Token vault controlled by program
seeds = [b"vault", mint.key().as_ref()]
```

**Finding PDAs:**

```rust
// On-chain (Anchor handles this automatically)
#[account(
    init,
    seeds = [b"profile", user.key().as_ref()],
    bump,
)]
pub profile: Account<'info, Profile>,

// Off-chain (TypeScript)
const [pda, bump] = PublicKey.findProgramAddressSync(
    [Buffer.from("profile"), userPubkey.toBuffer()],
    programId
);
```

**The bump**: PDAs must be OFF the ed25519 curve. The bump (0-255) is decremented until a valid off-curve point is found. Store the bump to avoid re-searching (~4,500 CU savings)."""),

    ("How does Solana's rent system work?",
     """Every account on Solana must maintain a minimum lamport balance proportional to its data size:

**Rent exemption formula:**
```
minimum_balance = (128 + data_size) × rent_rate × 2_years
```

**Current rates (~approximate):**
- Empty account (0 bytes): ~890,880 lamports (~0.00089 SOL)
- Typical program account (200 bytes): ~1,447,680 lamports
- Token account (165 bytes): ~2,039,280 lamports
- 10KB account: ~79,747,200 lamports

```rust
// Get rent-exempt minimum in a program
let rent = Rent::get()?;
let min_balance = rent.minimum_balance(data_len);

// Anchor handles this automatically with init:
#[account(
    init,
    payer = user,
    space = 8 + MyAccount::INIT_SPACE,  // Anchor calculates rent
)]
pub my_account: Account<'info, MyAccount>,
```

**Key facts:**
1. All accounts should be rent-exempt (hold ≥2 years of rent)
2. Rent-exempt accounts are NEVER charged rent
3. Non-exempt accounts are charged rent every epoch and deleted if balance reaches 0
4. Anchor's `init` constraint automatically makes accounts rent-exempt
5. When closing accounts (`close` constraint), rent lamports are returned

**Account space calculation:**
```rust
#[account]
#[derive(InitSpace)]
pub struct MyAccount {
    pub authority: Pubkey,     // 32 bytes
    #[max_len(50)]
    pub name: String,          // 4 + 50 bytes
    pub balance: u64,          // 8 bytes
    pub is_active: bool,       // 1 byte
    pub bump: u8,              // 1 byte
}
// Total: 8 (discriminator) + 32 + 54 + 8 + 1 + 1 = 104 bytes
```"""),
]

for question, answer in CONCEPTS:
    PAIRS.append(("concepts", m(question, answer)))


# ═══════════════════════════════════════════════════════════════════════════════
# Anchor CLI & Tooling
# ═══════════════════════════════════════════════════════════════════════════════

TOOLING = [
    ("set up a new Anchor project",
     """```bash
# Install Anchor CLI (requires Rust + Solana CLI)
cargo install --git https://github.com/coral-xyz/anchor avm --force
avm install latest
avm use latest

# Create new project
anchor init my_program
cd my_program

# Project structure:
# my_program/
# ├── Anchor.toml          # Project config
# ├── Cargo.toml            # Workspace config
# ├── programs/
# │   └── my_program/
# │       ├── Cargo.toml    # Program dependencies
# │       └── src/
# │           └── lib.rs    # Program code
# ├── tests/
# │   └── my_program.ts    # TypeScript tests
# ├── app/                  # Frontend (optional)
# └── migrations/
#     └── deploy.ts

# Build
anchor build

# Test (starts local validator + deploys + runs tests)
anchor test

# Deploy to devnet
anchor deploy --provider.cluster devnet
```

**Anchor.toml key settings:**
```toml
[features]
seeds = false
skip-lint = false

[programs.localnet]
my_program = "YOUR_PROGRAM_ID"

[provider]
cluster = "Localnet"
wallet = "~/.config/solana/id.json"
```"""),

    ("use Anchor's IDL for client generation",
     """After `anchor build`, the IDL (Interface Description Language) is generated at `target/idl/my_program.json`:

```typescript
// Import generated types
import { MyProgram } from "../target/types/my_program";
import idl from "../target/idl/my_program.json";

// Create program instance from IDL
const program = new anchor.Program<MyProgram>(
  idl as any,
  provider
);

// The IDL provides:
// 1. Typed methods for each instruction
program.methods.initialize(/* typed args */)

// 2. Typed account fetchers
const data = await program.account.myAccount.fetch(pubkey);
// data is fully typed — TypeScript knows all fields

// 3. Event types
program.addEventListener("myEvent", (event, slot) => {
  // event is typed
});

// Publish IDL on-chain (for Anchor explorer/debugging)
anchor idl init --filepath target/idl/my_program.json PROGRAM_ID
anchor idl upgrade --filepath target/idl/my_program.json PROGRAM_ID
```

The IDL is Solana's equivalent of Ethereum's ABI. It describes all instructions, accounts, types, events, and errors."""),

    ("debug a failed Anchor transaction",
     """Step-by-step debugging:

```bash
# 1. Check transaction logs
solana confirm -v <SIGNATURE>

# 2. Use Anchor's error parsing
anchor test -- --verbose

# 3. Simulate before sending
```

```typescript
// In tests, catch and inspect errors:
try {
  await program.methods.myInstruction().accounts({...}).rpc();
} catch (err) {
  if (err instanceof anchor.AnchorError) {
    console.log("Program error:", err.error.errorCode.code);
    console.log("Message:", err.error.errorMessage);
    console.log("Logs:", err.logs);
  }
}

// Simulate to see compute usage and logs:
const result = await program.methods
  .myInstruction()
  .accounts({...})
  .simulate();
console.log("CU used:", result.raw.value.unitsConsumed);
console.log("Logs:", result.raw.value.logs);
```

**Common errors:**
- `AccountNotInitialized`: Account doesn't exist or wrong program
- `ConstraintHasOne`: `has_one` check failed — wrong authority
- `ConstraintSeeds`: PDA seeds don't match
- `AccountDidNotDeserialize`: Wrong account type or corrupted data
- `InsufficientFunds`: Not enough SOL for rent
- `0x1`: Insufficient funds for token transfer
- `0x0`: Custom program error — check your `#[error_code]`"""),

    ("configure Anchor.toml for different environments",
     """```toml
# Anchor.toml

[toolchain]
anchor_version = "0.30.1"
solana_version = "1.18.17"

[features]
seeds = false
skip-lint = false
resolution = true

[programs.localnet]
my_program = "Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS"

[programs.devnet]
my_program = "Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS"

[programs.mainnet]
my_program = "PRODUCTION_PROGRAM_ID_HERE"

[registry]
url = "https://api.apr.dev"

[provider]
cluster = "Localnet"
wallet = "~/.config/solana/id.json"

[scripts]
test = "yarn run ts-mocha -p ./tsconfig.json -t 1000000 tests/**/*.ts"

# Test validator settings
[test.validator]
url = "https://api.mainnet-beta.solana.com"  # Fork mainnet state
startup_wait = 5000

[[test.validator.clone]]
address = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

[[test.validator.account]]
address = "YOUR_ACCOUNT"
filename = "tests/fixtures/account.json"
```

**Switch clusters:**
```bash
# Deploy to devnet
anchor deploy --provider.cluster devnet

# Run tests against devnet
anchor test --provider.cluster devnet --skip-local-validator

# Verify program on-chain
anchor verify PROGRAM_ID --provider.cluster mainnet
```"""),
]

for desc, code in TOOLING:
    q = f"How do I {desc}?"
    a = code
    PAIRS.append(("tooling", m(q, a)))


# ═══════════════════════════════════════════════════════════════════════════════
# Token Extensions (Token-2022)
# ═══════════════════════════════════════════════════════════════════════════════

TOKEN_EXTENSIONS = [
    ("transfer fee extension",
     "How do I create a token with transfer fees using Token-2022?",
     """```rust
use anchor_lang::prelude::*;
use anchor_spl::token_2022::{self, Token2022};
use spl_token_2022::extension::transfer_fee::TransferFeeConfig;

// Token-2022 supports built-in transfer fees:
// - Fee is automatically deducted on every transfer
// - Collected fees go to a designated fee account
// - Fee can be a percentage (basis points) + maximum cap

// In Anchor, use Token2022 instead of Token:
#[derive(Accounts)]
pub struct TransferWithFee<'info> {
    #[account(mut)]
    pub source: InterfaceAccount<'info, TokenAccount>,
    #[account(mut)]
    pub destination: InterfaceAccount<'info, TokenAccount>,
    pub authority: Signer<'info>,
    pub token_program: Program<'info, Token2022>,
}
```

Create the mint with transfer fee extension via CLI:
```bash
spl-token create-token --program-id TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb \\
  --transfer-fee 50 1000000  # 0.5% fee, max 1M tokens per transfer
```

Token-2022 extensions: Transfer Fees, Interest-Bearing, Non-Transferable, Permanent Delegate, Transfer Hook, Confidential Transfers, Metadata."""),

    ("metadata extension",
     "How do I add on-chain metadata to a token using Token-2022?",
     """Token-2022 has a built-in metadata extension — no separate Metaplex needed:

```bash
# Create token with metadata extension
spl-token create-token --program-id TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb \\
  --enable-metadata

# Initialize metadata
spl-token initialize-metadata <MINT> "My Token" "MTK" "https://example.com/metadata.json"

# Update metadata field
spl-token update-metadata <MINT> name "New Name"
spl-token update-metadata <MINT> uri "https://example.com/new-metadata.json"
```

```typescript
// In TypeScript
import { createInitializeMetadataPointerInstruction } from "@solana/spl-token";

const metadataPointerIx = createInitializeMetadataPointerInstruction(
  mint,
  authority,
  mint, // metadata stored on the mint itself
  TOKEN_2022_PROGRAM_ID
);
```

**Advantages over Metaplex:**
- No separate account needed (metadata stored on the mint)
- Lower cost (no Metaplex fees)
- Simpler integration
- Native to the token program"""),
]

for title, question, answer in TOKEN_EXTENSIONS:
    PAIRS.append(("token-extensions", m(question, answer)))


# ═══════════════════════════════════════════════════════════════════════════════
# Write output
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = [rec(content, category=cat) for cat, content in PAIRS]
    out_path = OUT_DIR / "synthetic-bulk2.jsonl"
    count = write_jsonl(records, out_path)
    print(f"Generated {count} records → {out_path}")


if __name__ == "__main__":
    main()
