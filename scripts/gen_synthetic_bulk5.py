#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 5: More Evol chains, OSS seeds, DPO pairs, common Q&A.

Target: ~200+ pairs. Focus on practical Q&A, common pitfalls, and more Evol/OSS.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from schema import Record, write_jsonl

SYSTEM = "You are an expert Solana and Anchor developer. Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns."
OUT_DIR = Path(__file__).parent.parent / "data" / "processed"

def m(u, a):
    return json.dumps([{"role":"system","content":SYSTEM},{"role":"user","content":u},{"role":"assistant","content":a}], ensure_ascii=False)

def rec(content, method="glan", category=""):
    meta = {"method": method, "collected_at": "2026-03-27"}
    if category: meta["category"] = category
    return Record(id=Record.make_id(content), source=f"synthetic/{method}", source_type="qa", content=content, language="rust", license="synthetic-claude", metadata=meta)

GLAN = []
EVOL = []
DPO_C = []
DPO_R = []
OSS = []

# ═══════════════════════════════════════════════════════════════════════════════
# Practical Q&A — things devs actually ask
# ═══════════════════════════════════════════════════════════════════════════════

QA = [
    ("What's the maximum account size on Solana?",
     """The maximum account size on Solana is **10 MB** (10,485,760 bytes). However, there are practical limits:

- **Per-transaction allocation**: You can only allocate up to **10 KB** in a single `create_account` instruction
- **realloc limit**: Max **10 KB increase** per `realloc` call per instruction
- **Cost**: A 10 MB account costs ~71.5 SOL in rent-exemption
- **CU cost**: Loading large accounts consumes more compute units

For most programs, keep accounts under 10 KB. For larger data:
1. Use **zero-copy** (`#[account(zero_copy)]`) to avoid full deserialization
2. Split data across multiple accounts
3. Use a linked list or tree of smaller accounts

```rust
// For large allocations, grow incrementally:
pub fn grow_account(ctx: Context<Grow>) -> Result<()> {
    // Can grow up to 10KB per instruction
    let new_size = ctx.accounts.data.to_account_info().data_len() + 10_000;
    ctx.accounts.data.to_account_info().realloc(new_size, false)?;
    Ok(())
}
```"""),

    ("How many accounts can I pass in a single Solana transaction?",
     """**Standard transactions**: Up to **64 unique accounts** (limited by transaction size of 1,232 bytes — each account key is 32 bytes).

**With Address Lookup Tables (ALTs)**: Up to **256 accounts** per lookup table. Referenced accounts only cost 1 byte (index) instead of 32 bytes.

```typescript
// Without ALT: ~35 accounts max in practice (other data takes space)
// With ALT: 100+ accounts possible

// Create ALT
const [createIx, lookupTable] = AddressLookupTableProgram.createLookupTable({
  authority: wallet.publicKey,
  payer: wallet.publicKey,
  recentSlot: await connection.getSlot(),
});

// Extend with addresses
const extendIx = AddressLookupTableProgram.extendLookupTable({
  lookupTable,
  authority: wallet.publicKey,
  payer: wallet.publicKey,
  addresses: [addr1, addr2, addr3, /* ... up to 30 per extend */],
});
```

If you need more than ~35 accounts, use versioned transactions with ALTs. If you need more than 256, split into multiple transactions."""),

    ("How do I handle the 'account data too small' error in Anchor?",
     """This error means the account doesn't have enough allocated space. Common causes:

```rust
// Cause 1: Wrong space calculation
// ❌ Forgot to include 8-byte discriminator
#[account(init, payer = user, space = MyAccount::INIT_SPACE)]
// ✅ Include the discriminator
#[account(init, payer = user, space = 8 + MyAccount::INIT_SPACE)]

// Cause 2: String/Vec exceeds max_len
#[account]
#[derive(InitSpace)]
pub struct MyAccount {
    #[max_len(32)]  // Only 32 bytes allocated for this String
    pub name: String,
}
// If you try to store a 50-byte string → account data too small

// Cause 3: Account already exists with smaller size
// Solution: Use realloc to grow it
#[account(
    mut,
    realloc = 8 + MyAccountV2::INIT_SPACE,
    realloc::payer = user,
    realloc::zero = false,
)]
pub my_account: Account<'info, MyAccountV2>,
```

Debug tip: Add up your actual sizes manually and compare with `INIT_SPACE`:
- Pubkey: 32, u64/i64: 8, u32: 4, u16: 2, u8/bool: 1
- String: 4 (length prefix) + max_len
- Vec<T>: 4 (length prefix) + max_len * size_of::<T>()
- Option<T>: 1 + size_of::<T>()"""),

    ("Why am I getting 'Error: Signature verification failed' in Anchor tests?",
     """Common causes and fixes:

```typescript
// Cause 1: Missing signer
// ❌ Forgot to add the keypair as a signer
await program.methods.myInstruction()
  .accounts({ authority: newKeypair.publicKey })
  .rpc(); // Missing .signers([newKeypair])

// ✅ Add the signer
await program.methods.myInstruction()
  .accounts({ authority: newKeypair.publicKey })
  .signers([newKeypair])
  .rpc();

// Cause 2: Wrong keypair
// The account passed doesn't match the actual signer
const alice = Keypair.generate();
const bob = Keypair.generate();
await program.methods.transfer()
  .accounts({ authority: alice.publicKey }) // account says alice
  .signers([bob]) // but bob is signing!
  .rpc();

// Cause 3: PDA passed where signer expected
// PDAs can't sign client-side — they sign via CPI in the program

// Cause 4: Provider wallet not funding the new keypair
const user = Keypair.generate();
// Airdrop before using:
const sig = await connection.requestAirdrop(user.publicKey, LAMPORTS_PER_SOL);
await connection.confirmTransaction(sig);
```"""),

    ("How do I test time-dependent logic in Anchor tests?",
     """Two approaches:

**1. Bankrun (recommended) — actual time warping:**
```typescript
import { startAnchor } from "solana-bankrun";

const context = await startAnchor(".", [], []);
const provider = new BankrunProvider(context);

// Advance time by 1 day
const currentClock = await context.banksClient.getClock();
context.setClock({
  ...currentClock,
  unixTimestamp: BigInt(currentClock.unixTimestamp) + BigInt(86400),
});

// Now Clock::get()? in your program returns the warped time
await program.methods.claimRewards().accounts({...}).rpc();
```

**2. Local validator — advance slots:**
```typescript
// Less precise, but works with anchor test
import { sleep } from "@coral-xyz/anchor/dist/cjs/utils/common";

// Create time-sensitive data
await program.methods.createLock(new anchor.BN(lockDuration)).rpc();

// Wait for real time to pass (slow for long durations)
await sleep(lockDuration * 1000);

// Or: use a configurable time source in your program
// Pass a mock clock account in tests
```

Bankrun is strongly preferred for time-dependent tests — it's instant and deterministic."""),

    ("What's the difference between `Account`, `UncheckedAccount`, `SystemAccount`, and `Signer` in Anchor?",
     """```rust
#[derive(Accounts)]
pub struct Example<'info> {
    // Account<'info, T> — Fully validated program-owned account
    // ✓ Checks owner == your program
    // ✓ Deserializes and validates discriminator
    // ✓ Type-safe access to fields
    #[account(mut)]
    pub my_data: Account<'info, MyStruct>,

    // Signer<'info> — Verifies the account signed the transaction
    // ✓ Checks is_signer == true
    // ✗ No owner check, no deserialization
    pub authority: Signer<'info>,

    // SystemAccount<'info> — Account owned by the System Program
    // ✓ Checks owner == System Program
    // ✗ No deserialization
    // Use for: SOL-holding PDAs, recipients of SOL transfers
    #[account(mut)]
    pub vault: SystemAccount<'info>,

    // UncheckedAccount<'info> — No validation at all
    // ✗ No owner check, no signer check, no deserialization
    // REQUIRES /// CHECK: comment explaining why it's safe
    // Use for: accounts validated by other means (constraints, CPIs)
    /// CHECK: Validated by CPI to token program
    #[account(mut)]
    pub external: UncheckedAccount<'info>,

    // Program<'info, T> — Verified program account
    // ✓ Checks account is executable
    // ✓ Checks program ID matches T
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,

    // InterfaceAccount<'info, T> — For Token-2022 compatibility
    // Works with both Token and Token-2022 programs
    pub token_account: InterfaceAccount<'info, TokenAccount>,
}
```

**Decision tree:**
1. Is it your program's data? → `Account<'info, T>`
2. Must it sign? → `Signer<'info>`
3. Just holds SOL? → `SystemAccount<'info>`
4. Is it a program? → `Program<'info, T>`
5. Need Token-2022 compat? → `InterfaceAccount<'info, T>`
6. Validated by other means? → `UncheckedAccount<'info>` + `/// CHECK:`"""),

    ("How do I handle large data structures that don't fit in a single account?",
     """Split data across multiple linked accounts:

```rust
use anchor_lang::prelude::*;

// Pattern 1: Chunked storage with linked list
#[account]
#[derive(InitSpace)]
pub struct DataChunk {
    pub owner: Pubkey,
    pub chunk_index: u32,
    pub next_chunk: Option<Pubkey>,  // linked list
    #[max_len(9000)]                // ~9KB of data per chunk
    pub data: Vec<u8>,
    pub bump: u8,
}

// Pattern 2: Index + data separation
#[account]
#[derive(InitSpace)]
pub struct CollectionIndex {
    pub authority: Pubkey,
    pub item_count: u32,
    pub total_data_size: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct CollectionItem {
    pub collection: Pubkey,
    pub index: u32,
    #[max_len(512)]
    pub key: String,
    #[max_len(8000)]
    pub value: Vec<u8>,
    pub bump: u8,
}

// Items are PDAs: seeds = [b"item", collection.key(), &index.to_le_bytes()]

// Pattern 3: For append-only logs, use account compression (Noop program)
// This stores data in transaction logs, not in accounts
// Used by Metaplex Bubblegum for compressed NFTs
```

Rules of thumb:
- < 10 KB: Single account is fine
- 10 KB - 1 MB: Zero-copy + single account
- 1 MB+: Split across multiple accounts with indexing
- Append-only: Consider account compression"""),

    ("How do I implement a program that calls another Anchor program?",
     """```rust
// Program A: The caller
use anchor_lang::prelude::*;

// Import Program B's IDL types
// In Anchor 0.30+, use declare_program!:
// For older versions, add B as a crate dependency

declare_id!("ProgramA1111111111111111111111111111111111");

#[program]
pub mod program_a {
    use super::*;

    pub fn call_program_b(ctx: Context<CallB>, amount: u64) -> Result<()> {
        // Build CPI to Program B
        let cpi_program = ctx.accounts.program_b.to_account_info();

        let cpi_accounts = program_b::cpi::accounts::Deposit {
            user: ctx.accounts.user.to_account_info(),
            vault: ctx.accounts.vault.to_account_info(),
            system_program: ctx.accounts.system_program.to_account_info(),
        };

        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        program_b::cpi::deposit(cpi_ctx, amount)?;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct CallB<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    /// CHECK: Program B's vault PDA
    #[account(mut)]
    pub vault: UncheckedAccount<'info>,
    pub program_b: Program<'info, ProgramBType>,
    pub system_program: Program<'info, System>,
}
```

**Steps:**
1. Add Program B as a Cargo dependency or use `declare_program!`
2. Import B's account types and CPI module
3. Build `CpiContext` with B's account struct
4. Call `program_b::cpi::instruction_name()`

For PDA-signed CPI: use `CpiContext::new_with_signer` with Program A's PDA seeds."""),

    ("What are the best practices for Anchor program security?",
     """Security checklist for Anchor programs:

**1. Account validation (most common vulnerabilities):**
```rust
// ✅ Always use typed accounts
pub vault: Account<'info, Vault>,        // NOT UncheckedAccount
pub user: Signer<'info>,                  // NOT AccountInfo
pub token_program: Program<'info, Token>, // NOT UncheckedAccount

// ✅ Always verify authority
#[account(has_one = authority)]

// ✅ Always verify PDA seeds + bump
#[account(seeds = [...], bump = account.bump)]

// ✅ Verify token account relationships
#[account(
    constraint = user_token.mint == expected_mint,
    constraint = user_token.owner == user.key(),
)]
```

**2. Arithmetic safety:**
```rust
// ✅ Use checked math everywhere
amount.checked_add(fee).ok_or(MyError::Overflow)?
// ✅ Use u128 for intermediate products
(a as u128).checked_mul(b as u128)
// ✅ Check for zero before division
require!(divisor > 0, MyError::DivByZero);
```

**3. Instruction ordering:**
```rust
// ✅ Checks-effects-interactions pattern
// 1. Validate all inputs (checks)
require!(amount > 0, MyError::ZeroAmount);
// 2. Update state (effects)
vault.balance -= amount;
// 3. External calls last (interactions)
token::transfer(...)?;
```

**4. Common pitfalls to avoid:**
- Don't use `UncheckedAccount` without thorough manual validation
- Don't skip `has_one` for authority fields
- Don't use raw `AccountInfo::lamports` for balance checks (could change between instructions)
- Don't assume account data is valid without discriminator checks
- Don't forget `close` constraint zeros data (prevents resurrection)
- Don't use `init_if_needed` without understanding the risks (someone else could init first)"""),

    ("How do I set up a local development environment for Solana?",
     """```bash
# 1. Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 2. Install Solana CLI
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"

# 3. Create a wallet
solana-keygen new --outfile ~/.config/solana/id.json
solana config set --url localhost  # or devnet

# 4. Install Anchor
cargo install --git https://github.com/coral-xyz/anchor avm --force
avm install latest
avm use latest

# 5. Install Node.js dependencies
npm install -g yarn
yarn global add ts-mocha typescript

# 6. Create and test a project
anchor init my_project
cd my_project
anchor test  # Builds, starts validator, deploys, runs tests

# Useful commands:
solana-test-validator          # Start local validator manually
solana logs                    # Stream program logs
solana balance                 # Check wallet balance
solana airdrop 5               # Get SOL on devnet/localnet
anchor build                   # Build without testing
anchor test --skip-local-validator  # Test against running validator
```

**VS Code extensions:**
- Rust Analyzer (rust-lang.rust-analyzer)
- Anchor (anchor-lang) — syntax highlighting for Anchor attributes"""),

    ("How do I handle token accounts with Token-2022 compatibility?",
     """Use Anchor's `Interface` types for dual Token/Token-2022 support:

```rust
use anchor_lang::prelude::*;
use anchor_spl::{
    token_interface::{self, Mint, TokenAccount, TokenInterface, TransferChecked},
};

#[program]
pub mod compatible {
    use super::*;

    pub fn transfer(ctx: Context<Transfer>, amount: u64) -> Result<()> {
        let mint = &ctx.accounts.mint;
        let decimals = mint.decimals;

        // transfer_checked works with both Token and Token-2022
        token_interface::transfer_checked(
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
            decimals,
        )?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Transfer<'info> {
    // InterfaceAccount works with both Token and Token-2022
    #[account(mut)]
    pub from: InterfaceAccount<'info, TokenAccount>,
    pub mint: InterfaceAccount<'info, Mint>,
    #[account(mut)]
    pub to: InterfaceAccount<'info, TokenAccount>,
    pub authority: Signer<'info>,
    // TokenInterface accepts both program IDs
    pub token_program: Interface<'info, TokenInterface>,
}
```

Key changes from Token-only code:
- `Account<'info, TokenAccount>` → `InterfaceAccount<'info, TokenAccount>`
- `Program<'info, Token>` → `Interface<'info, TokenInterface>`
- `token::transfer` → `token_interface::transfer_checked` (Token-2022 requires checked variant)
- Import from `anchor_spl::token_interface` instead of `anchor_spl::token`"""),
]

for question, answer in QA:
    GLAN.append(("qa", m(question, answer)))


# ═══════════════════════════════════════════════════════════════════════════════
# More Evol-Instruct Chains
# ═══════════════════════════════════════════════════════════════════════════════

# ── Chain: Token Launchpad ──────────────────────────────────────────────────

EVOL.append(("launchpad-L0", m(
    "Write an Anchor program that creates a new SPL token with a fixed supply.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, MintTo, Token, TokenAccount, SetAuthority};
use anchor_spl::associated_token::AssociatedToken;
use spl_token::instruction::AuthorityType;

declare_id!("11111111111111111111111111111111");

const TOTAL_SUPPLY: u64 = 1_000_000_000_000_000; // 1B tokens with 6 decimals

#[program]
pub mod token_creator {
    use super::*;

    pub fn create_token(ctx: Context<CreateToken>) -> Result<()> {
        // Mint total supply to creator
        token::mint_to(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), MintTo {
                mint: ctx.accounts.mint.to_account_info(),
                to: ctx.accounts.creator_ata.to_account_info(),
                authority: ctx.accounts.creator.to_account_info(),
            }),
            TOTAL_SUPPLY,
        )?;

        // Revoke mint authority — fixed supply
        token::set_authority(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), SetAuthority {
                current_authority: ctx.accounts.creator.to_account_info(),
                account_or_mint: ctx.accounts.mint.to_account_info(),
            }),
            AuthorityType::MintTokens,
            None,
        )?;

        msg!("Created token with {} supply", TOTAL_SUPPLY);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CreateToken<'info> {
    #[account(mut)]
    pub creator: Signer<'info>,
    #[account(init, payer = creator, mint::decimals = 6, mint::authority = creator)]
    pub mint: Account<'info, Mint>,
    #[account(init, payer = creator, associated_token::mint = mint, associated_token::authority = creator)]
    pub creator_ata: Account<'info, TokenAccount>,
    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
}
```""")))

EVOL.append(("launchpad-L1", m(
    "Extend the token creator into a fair launch: users deposit SOL during a sale period, then claim tokens proportionally based on their contribution.",
    """```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Transfer, Token, TokenAccount};
use anchor_spl::associated_token::AssociatedToken;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod fair_launch {
    use super::*;

    pub fn initialize_sale(
        ctx: Context<InitSale>,
        tokens_for_sale: u64,
        start_time: i64,
        end_time: i64,
    ) -> Result<()> {
        require!(end_time > start_time, LaunchError::InvalidTime);
        require!(tokens_for_sale > 0, LaunchError::ZeroAmount);

        let sale = &mut ctx.accounts.sale;
        sale.authority = ctx.accounts.authority.key();
        sale.mint = ctx.accounts.mint.key();
        sale.tokens_for_sale = tokens_for_sale;
        sale.total_deposited = 0;
        sale.start_time = start_time;
        sale.end_time = end_time;
        sale.is_finalized = false;
        sale.bump = ctx.bumps.sale;

        // Transfer tokens to sale vault
        token::transfer(
            CpiContext::new(ctx.accounts.token_program.to_account_info(), Transfer {
                from: ctx.accounts.authority_ata.to_account_info(),
                to: ctx.accounts.sale_vault.to_account_info(),
                authority: ctx.accounts.authority.to_account_info(),
            }),
            tokens_for_sale,
        )?;
        Ok(())
    }

    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        let sale = &ctx.accounts.sale;
        let clock = Clock::get()?;
        require!(clock.unix_timestamp >= sale.start_time, LaunchError::NotStarted);
        require!(clock.unix_timestamp <= sale.end_time, LaunchError::SaleEnded);
        require!(amount > 0, LaunchError::ZeroAmount);

        // Deposit SOL
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.buyer.key(),
            &ctx.accounts.sol_vault.key(),
            amount,
        );
        anchor_lang::solana_program::program::invoke(&ix, &[
            ctx.accounts.buyer.to_account_info(),
            ctx.accounts.sol_vault.to_account_info(),
        ])?;

        let deposit = &mut ctx.accounts.buyer_deposit;
        deposit.buyer = ctx.accounts.buyer.key();
        deposit.amount = deposit.amount.checked_add(amount).ok_or(LaunchError::MathOverflow)?;
        deposit.has_claimed = false;
        deposit.bump = ctx.bumps.buyer_deposit;

        let sale = &mut ctx.accounts.sale;
        sale.total_deposited = sale.total_deposited
            .checked_add(amount).ok_or(LaunchError::MathOverflow)?;
        Ok(())
    }

    pub fn claim_tokens(ctx: Context<ClaimTokens>) -> Result<()> {
        let sale = &ctx.accounts.sale;
        let clock = Clock::get()?;
        require!(clock.unix_timestamp > sale.end_time, LaunchError::SaleNotEnded);
        require!(sale.total_deposited > 0, LaunchError::NoDeposits);

        let deposit = &mut ctx.accounts.buyer_deposit;
        require!(!deposit.has_claimed, LaunchError::AlreadyClaimed);

        // Calculate proportional share
        let user_share = (sale.tokens_for_sale as u128)
            .checked_mul(deposit.amount as u128).ok_or(LaunchError::MathOverflow)?
            .checked_div(sale.total_deposited as u128).ok_or(LaunchError::MathOverflow)? as u64;

        // Transfer tokens from vault via PDA
        let seeds = &[b"sale".as_ref(), sale.mint.as_ref(), &[sale.bump]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.sale_vault.to_account_info(),
                    to: ctx.accounts.buyer_ata.to_account_info(),
                    authority: ctx.accounts.sale.to_account_info(),
                },
                &[seeds],
            ),
            user_share,
        )?;

        deposit.has_claimed = true;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Sale {
    pub authority: Pubkey,
    pub mint: Pubkey,
    pub tokens_for_sale: u64,
    pub total_deposited: u64,
    pub start_time: i64,
    pub end_time: i64,
    pub is_finalized: bool,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct BuyerDeposit {
    pub buyer: Pubkey,
    pub amount: u64,
    pub has_claimed: bool,
    pub bump: u8,
}

#[error_code]
pub enum LaunchError {
    #[msg("Invalid time range")] InvalidTime,
    #[msg("Zero amount")] ZeroAmount,
    #[msg("Sale not started")] NotStarted,
    #[msg("Sale ended")] SaleEnded,
    #[msg("Sale not ended yet")] SaleNotEnded,
    #[msg("No deposits")] NoDeposits,
    #[msg("Already claimed")] AlreadyClaimed,
    #[msg("Math overflow")] MathOverflow,
}
```

Fair launch = everyone gets tokens proportional to their SOL contribution. No frontrunning advantage since the price is set after the sale ends.""")))


# ── Chain: Prediction Market ──────────────────────────────────────────────

EVOL.append(("prediction-L0", m(
    "Write an Anchor program for a binary prediction market where users bet YES or NO on an outcome.",
    """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

#[program]
pub mod prediction_market {
    use super::*;

    pub fn create_market(
        ctx: Context<CreateMarket>,
        question: String,
        resolution_time: i64,
    ) -> Result<()> {
        require!(question.len() <= 200, MarketError::QuestionTooLong);
        let clock = Clock::get()?;
        require!(resolution_time > clock.unix_timestamp, MarketError::InvalidTime);

        let market = &mut ctx.accounts.market;
        market.creator = ctx.accounts.creator.key();
        market.question = question;
        market.resolution_time = resolution_time;
        market.yes_pool = 0;
        market.no_pool = 0;
        market.resolved = false;
        market.outcome = false;
        market.bump = ctx.bumps.market;
        Ok(())
    }

    pub fn place_bet(ctx: Context<PlaceBet>, is_yes: bool, amount: u64) -> Result<()> {
        let market = &ctx.accounts.market;
        let clock = Clock::get()?;
        require!(clock.unix_timestamp < market.resolution_time, MarketError::BettingClosed);
        require!(!market.resolved, MarketError::AlreadyResolved);
        require!(amount > 0, MarketError::ZeroAmount);

        // Transfer SOL to market pool
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.bettor.key(),
            &ctx.accounts.pool.key(),
            amount,
        );
        anchor_lang::solana_program::program::invoke(&ix, &[
            ctx.accounts.bettor.to_account_info(),
            ctx.accounts.pool.to_account_info(),
        ])?;

        let bet = &mut ctx.accounts.bet;
        bet.bettor = ctx.accounts.bettor.key();
        bet.market = ctx.accounts.market.key();
        bet.is_yes = is_yes;
        bet.amount = amount;
        bet.claimed = false;
        bet.bump = ctx.bumps.bet;

        let market = &mut ctx.accounts.market;
        if is_yes {
            market.yes_pool = market.yes_pool.checked_add(amount).ok_or(MarketError::Overflow)?;
        } else {
            market.no_pool = market.no_pool.checked_add(amount).ok_or(MarketError::Overflow)?;
        }
        Ok(())
    }

    pub fn resolve(ctx: Context<Resolve>, outcome: bool) -> Result<()> {
        let market = &mut ctx.accounts.market;
        let clock = Clock::get()?;
        require!(clock.unix_timestamp >= market.resolution_time, MarketError::TooEarly);
        require!(!market.resolved, MarketError::AlreadyResolved);

        market.resolved = true;
        market.outcome = outcome;
        Ok(())
    }

    pub fn claim_winnings(ctx: Context<ClaimWinnings>) -> Result<()> {
        let market = &ctx.accounts.market;
        let bet = &mut ctx.accounts.bet;
        require!(market.resolved, MarketError::NotResolved);
        require!(!bet.claimed, MarketError::AlreadyClaimed);
        require!(bet.is_yes == market.outcome, MarketError::DidNotWin);

        let total_pool = market.yes_pool.checked_add(market.no_pool).ok_or(MarketError::Overflow)?;
        let winning_pool = if market.outcome { market.yes_pool } else { market.no_pool };

        // Proportional winnings: (bet_amount / winning_pool) * total_pool
        let winnings = (bet.amount as u128)
            .checked_mul(total_pool as u128).ok_or(MarketError::Overflow)?
            .checked_div(winning_pool as u128).ok_or(MarketError::Overflow)? as u64;

        let pool = &ctx.accounts.pool;
        **pool.to_account_info().try_borrow_mut_lamports()? -= winnings;
        **ctx.accounts.bettor.to_account_info().try_borrow_mut_lamports()? += winnings;

        bet.claimed = true;
        Ok(())
    }
}

#[account]
#[derive(InitSpace)]
pub struct Market {
    pub creator: Pubkey,
    #[max_len(200)]
    pub question: String,
    pub resolution_time: i64,
    pub yes_pool: u64,
    pub no_pool: u64,
    pub resolved: bool,
    pub outcome: bool,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Bet {
    pub bettor: Pubkey,
    pub market: Pubkey,
    pub is_yes: bool,
    pub amount: u64,
    pub claimed: bool,
    pub bump: u8,
}

#[error_code]
pub enum MarketError {
    #[msg("Question too long")] QuestionTooLong,
    #[msg("Invalid time")] InvalidTime,
    #[msg("Betting closed")] BettingClosed,
    #[msg("Already resolved")] AlreadyResolved,
    #[msg("Zero amount")] ZeroAmount,
    #[msg("Too early to resolve")] TooEarly,
    #[msg("Not resolved yet")] NotResolved,
    #[msg("Already claimed")] AlreadyClaimed,
    #[msg("Did not win")] DidNotWin,
    #[msg("Math overflow")] Overflow,
}
```""")))


# ── More OSS-Instruct seeds ──────────────────────────────────────────────

OSS_SEEDS = [
    ("referral_system",
     "Given this code seed, build a complete Anchor program:\n```rust\npub referrer: Option<Pubkey>,\npub referral_count: u32,\npub fn register(referrer_code) {}\npub fn get_discount() -> u16 {}\n```",
     """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

const BASE_DISCOUNT_BPS: u16 = 0;
const PER_REFERRAL_BPS: u16 = 50;  // 0.5% per referral
const MAX_DISCOUNT_BPS: u16 = 1000; // 10% max

#[program]
pub mod referral_system {
    use super::*;

    pub fn register(ctx: Context<Register>) -> Result<()> {
        let profile = &mut ctx.accounts.profile;
        profile.user = ctx.accounts.user.key();
        profile.referrer = None;
        profile.referral_count = 0;
        profile.total_earnings = 0;
        profile.bump = ctx.bumps.profile;
        Ok(())
    }

    pub fn register_with_referrer(ctx: Context<RegisterWithReferrer>) -> Result<()> {
        let profile = &mut ctx.accounts.profile;
        profile.user = ctx.accounts.user.key();
        profile.referrer = Some(ctx.accounts.referrer_profile.user);
        profile.referral_count = 0;
        profile.total_earnings = 0;
        profile.bump = ctx.bumps.profile;

        // Increment referrer's count
        let referrer = &mut ctx.accounts.referrer_profile;
        referrer.referral_count = referrer.referral_count
            .checked_add(1).ok_or(RefError::Overflow)?;
        Ok(())
    }

    pub fn get_discount(ctx: Context<GetDiscount>) -> Result<()> {
        let profile = &ctx.accounts.profile;
        let discount = std::cmp::min(
            BASE_DISCOUNT_BPS + profile.referral_count as u16 * PER_REFERRAL_BPS,
            MAX_DISCOUNT_BPS,
        );
        msg!("Discount for {}: {} bps", profile.user, discount);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Register<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(init, payer = user, space = 8 + ReferralProfile::INIT_SPACE, seeds = [b"profile", user.key().as_ref()], bump)]
    pub profile: Account<'info, ReferralProfile>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RegisterWithReferrer<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(init, payer = user, space = 8 + ReferralProfile::INIT_SPACE, seeds = [b"profile", user.key().as_ref()], bump)]
    pub profile: Account<'info, ReferralProfile>,
    #[account(mut, seeds = [b"profile", referrer_profile.user.as_ref()], bump = referrer_profile.bump)]
    pub referrer_profile: Account<'info, ReferralProfile>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct GetDiscount<'info> {
    pub user: Signer<'info>,
    #[account(seeds = [b"profile", user.key().as_ref()], bump = profile.bump)]
    pub profile: Account<'info, ReferralProfile>,
}

#[account]
#[derive(InitSpace)]
pub struct ReferralProfile {
    pub user: Pubkey,
    pub referrer: Option<Pubkey>,
    pub referral_count: u32,
    pub total_earnings: u64,
    pub bump: u8,
}

#[error_code]
pub enum RefError {
    #[msg("Math overflow")] Overflow,
}
```"""),

    ("badge_system",
     "Given this code seed, build a complete Anchor program:\n```rust\npub badges: [bool; 8],\npub fn award_badge(badge_id: u8) {}\npub fn has_badge(badge_id: u8) -> bool {}\n```",
     """```rust
use anchor_lang::prelude::*;

declare_id!("11111111111111111111111111111111");

const MAX_BADGES: usize = 64;

#[program]
pub mod badge_system {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let profile = &mut ctx.accounts.profile;
        profile.user = ctx.accounts.user.key();
        profile.badge_bits = 0u64; // Bitfield for 64 badges
        profile.badge_count = 0;
        profile.first_badge_at = 0;
        profile.bump = ctx.bumps.profile;
        Ok(())
    }

    pub fn award_badge(ctx: Context<AwardBadge>, badge_id: u8) -> Result<()> {
        require!((badge_id as usize) < MAX_BADGES, BadgeError::InvalidBadge);

        let profile = &mut ctx.accounts.profile;
        let mask = 1u64 << badge_id;

        require!(profile.badge_bits & mask == 0, BadgeError::AlreadyAwarded);

        profile.badge_bits |= mask;
        profile.badge_count += 1;
        if profile.first_badge_at == 0 {
            profile.first_badge_at = Clock::get()?.unix_timestamp;
        }

        emit!(BadgeAwarded {
            user: profile.user,
            badge_id,
            total_badges: profile.badge_count,
        });
        Ok(())
    }

    pub fn revoke_badge(ctx: Context<AwardBadge>, badge_id: u8) -> Result<()> {
        require!((badge_id as usize) < MAX_BADGES, BadgeError::InvalidBadge);

        let profile = &mut ctx.accounts.profile;
        let mask = 1u64 << badge_id;
        require!(profile.badge_bits & mask != 0, BadgeError::NotAwarded);

        profile.badge_bits &= !mask;
        profile.badge_count -= 1;
        Ok(())
    }

    pub fn check_badge(ctx: Context<CheckBadge>, badge_id: u8) -> Result<()> {
        let profile = &ctx.accounts.profile;
        let has_it = (profile.badge_bits >> badge_id) & 1 == 1;
        msg!("User {} has badge {}: {}", profile.user, badge_id, has_it);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(init, payer = user, space = 8 + BadgeProfile::INIT_SPACE, seeds = [b"badges", user.key().as_ref()], bump)]
    pub profile: Account<'info, BadgeProfile>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AwardBadge<'info> {
    pub admin: Signer<'info>,
    #[account(mut, seeds = [b"badges", profile.user.as_ref()], bump = profile.bump)]
    pub profile: Account<'info, BadgeProfile>,
    #[account(seeds = [b"config"], bump = config.bump, has_one = admin)]
    pub config: Account<'info, Config>,
}

#[derive(Accounts)]
pub struct CheckBadge<'info> {
    #[account(seeds = [b"badges", profile.user.as_ref()], bump = profile.bump)]
    pub profile: Account<'info, BadgeProfile>,
}

#[account]
#[derive(InitSpace)]
pub struct BadgeProfile {
    pub user: Pubkey,
    pub badge_bits: u64,  // Bitfield: up to 64 badges
    pub badge_count: u8,
    pub first_badge_at: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Config {
    pub admin: Pubkey,
    pub bump: u8,
}

#[event]
pub struct BadgeAwarded { pub user: Pubkey, pub badge_id: u8, pub total_badges: u8 }

#[error_code]
pub enum BadgeError {
    #[msg("Invalid badge ID")] InvalidBadge,
    #[msg("Badge already awarded")] AlreadyAwarded,
    #[msg("Badge not awarded")] NotAwarded,
}
```

Uses a bitfield (`u64`) for compact badge storage — 64 badges in a single 8-byte field. `badge_bits |= (1 << id)` sets a badge, `(badge_bits >> id) & 1` checks it."""),
]

for name, question, answer in OSS_SEEDS:
    OSS.append((name, m(question, answer)))


# ═══════════════════════════════════════════════════════════════════════════════
# More DPO pairs
# ═══════════════════════════════════════════════════════════════════════════════

MORE_DPO = [
    ("Should I use `init_if_needed` in my Anchor program?",
     # CHOSEN
     """`init_if_needed` is safe in specific cases but risky in others:

**Safe to use:**
- Associated Token Accounts (ATAs) — address is deterministic, can't be front-run with wrong data
- Config accounts with `seeds` that include the payer — only the intended user can init

**Risky — avoid:**
- Accounts where an attacker could initialize with malicious data before the intended user
- Accounts without constraints that validate the initializer

```rust
// ✅ Safe: ATA is deterministic
#[account(
    init_if_needed,
    payer = user,
    associated_token::mint = mint,
    associated_token::authority = user,
)]
pub user_ata: Account<'info, TokenAccount>,

// ⚠️ Risky: attacker could init this PDA with wrong authority
#[account(
    init_if_needed,
    payer = user,
    space = 8 + Vault::INIT_SPACE,
    seeds = [b"vault", mint.key().as_ref()],
    bump,
)]
pub vault: Account<'info, Vault>,
// An attacker could call this first with their own key as user,
// setting vault.authority to their address!

// ✅ Fix: Add constraint to verify authority after init
#[account(
    init_if_needed,
    payer = user,
    space = 8 + Vault::INIT_SPACE,
    seeds = [b"vault", mint.key().as_ref()],
    bump,
    constraint = vault.authority == Pubkey::default() || vault.authority == user.key() @ MyError::AlreadyInitialized,
)]
```

Enable with: `anchor-lang = { features = ["init-if-needed"] }`""",
     # REJECTED
     """`init_if_needed` is perfectly safe and should be used liberally. It saves gas by combining init and usage into one instruction:

```rust
#[account(
    init_if_needed,
    payer = user,
    space = 8 + MyAccount::INIT_SPACE,
    seeds = [b"data"],
    bump,
)]
pub data: Account<'info, MyAccount>,
```

Always use it instead of separate init instructions to save on transaction fees."""),

    ("How should I store strings in Solana accounts?",
     # CHOSEN
     """Use fixed-size strings with `#[max_len]` in Anchor:

```rust
#[account]
#[derive(InitSpace)]
pub struct Profile {
    pub authority: Pubkey,
    #[max_len(32)]
    pub name: String,        // 4 + 32 = 36 bytes allocated
    #[max_len(200)]
    pub bio: String,         // 4 + 200 = 204 bytes allocated
    pub bump: u8,
}
```

**Important considerations:**
1. Space is pre-allocated at `max_len` — short strings don't save space
2. The 4-byte length prefix stores actual string length
3. Validate string length in your instruction handler:
   ```rust
   require!(name.len() <= 32, MyError::NameTooLong);
   require!(!name.is_empty(), MyError::NameEmpty);
   ```
4. For UTF-8 strings, `len()` returns byte count, not character count
5. Consider sanitizing input (no null bytes, valid UTF-8)
6. If string content rarely changes, consider storing a hash on-chain and the full string off-chain (Arweave/IPFS)

For very long text (>1KB), store a URI/hash on-chain pointing to off-chain storage.""",
     # REJECTED
     """Use `Vec<u8>` for strings to avoid the String overhead:

```rust
#[account]
pub struct Profile {
    pub name: Vec<u8>, // Store as raw bytes
}
```

This is more efficient than String because it avoids UTF-8 validation overhead."""),
]

for question, chosen, rejected in MORE_DPO:
    DPO_C.append(("dpo", m(question, chosen)))
    DPO_R.append(("dpo", m(question, rejected)))


# ═══════════════════════════════════════════════════════════════════════════════
# Write all outputs
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_records = []

    # GLAN
    glan_records = [rec(content, category=cat) for cat, content in GLAN]
    glan_path = OUT_DIR / "synthetic-bulk5-glan.jsonl"
    c1 = write_jsonl(glan_records, glan_path)
    print(f"GLAN: {c1} records → {glan_path.name}")

    # Evol-Instruct
    evol_records = [rec(content, method="evol-instruct", category=cat) for cat, content in EVOL]
    evol_path = OUT_DIR / "synthetic-bulk5-evol.jsonl"
    c2 = write_jsonl(evol_records, evol_path)
    print(f"Evol: {c2} records → {evol_path.name}")

    # DPO
    dpo_c_records = [rec(content, method="dpo-chosen", category=cat) for cat, content in DPO_C]
    dpo_r_records = [rec(content, method="dpo-rejected", category=cat) for cat, content in DPO_R]
    c3 = write_jsonl(dpo_c_records, OUT_DIR / "dpo-chosen-bulk2.jsonl")
    c4 = write_jsonl(dpo_r_records, OUT_DIR / "dpo-rejected-bulk2.jsonl")
    print(f"DPO: {c3} chosen + {c4} rejected")

    # OSS
    oss_records = [rec(content, method="oss-instruct", category=cat) for cat, content in OSS]
    c5 = write_jsonl(oss_records, OUT_DIR / "synthetic-bulk5-oss.jsonl")
    print(f"OSS: {c5} records")

    print(f"\nTotal: {c1+c2+c3+c4+c5} records")


if __name__ == "__main__":
    main()
