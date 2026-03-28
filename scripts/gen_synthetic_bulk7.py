#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 7: Error handling & debugging.
Target: ~150 records covering custom errors, common runtime errors, debugging techniques.
"""
import hashlib, json
from pathlib import Path

PROCESSED = Path(__file__).parent.parent / "data" / "processed"

def make_rec(content, category, lang="rust"):
    return {
        "id": hashlib.sha256(content.encode()).hexdigest(),
        "source": "synthetic/glan",
        "source_type": "synthetic",
        "content": content,
        "language": lang,
        "license": "synthetic-original",
        "metadata": {"method": "glan", "category": category, "anchor_version_class": "modern"},
    }

records = []

# ── 1. Custom error codes (15 records) ──
PROGRAMS = [
    ("marketplace", ["ListingNotActive", "PriceMismatch", "SellerCannotBuy", "InsufficientPayment", "RoyaltyOverflow"]),
    ("staking", ["StakeAmountTooLow", "CooldownNotElapsed", "PoolCapReached", "RewardsAlreadyClaimed", "InvalidStakeState"]),
    ("governance", ["ProposalExpired", "QuorumNotReached", "AlreadyVoted", "InvalidProposalState", "TimelockNotElapsed"]),
    ("auction", ["AuctionEnded", "BidTooLow", "AuctionNotStarted", "SellerCannotBid", "WithdrawalLocked"]),
    ("lending", ["InsufficientCollateral", "BorrowCapExceeded", "OraclePriceStale", "HealthFactorTooLow", "MarketPaused"]),
]
for prog, errors in PROGRAMS:
    err_variants = "\n".join(f"    #[msg(\"{e.replace('Error','')}: operation failed\")]\n    {e}," for e in errors[:3])
    records.append(make_rec(
        f"### Question\nHow do I define custom error codes for a {prog} program in Anchor?\n\n### Answer\nUse the `#[error_code]` attribute on an enum:\n\n```rust\nuse anchor_lang::prelude::*;\n\n#[error_code]\npub enum {prog.title()}Error {{\n{err_variants}\n}}\n```\n\nUse them with `require!()` macros:\n```rust\nrequire!(condition, {prog.title()}Error::{errors[0]});\nrequire_keys_eq!(a.key(), b.key(), {prog.title()}Error::{errors[1]});\nrequire_gt!(amount, 0, {prog.title()}Error::{errors[2]});\n```\n\nEach variant gets an auto-assigned error code starting at 6000 (Anchor's custom error offset).",
        "custom_errors"
    ))

# require! variants for each program
for prog, errors in PROGRAMS:
    records.append(make_rec(
        f"### Question\nWhat are the different `require!` macros available in Anchor for a {prog} program?\n\n### Answer\nAnchor provides several `require!` variants:\n\n```rust\n// Basic boolean check\nrequire!(amount > 0, {prog.title()}Error::{errors[0]});\n\n// Key equality\nrequire_keys_eq!(\n    ctx.accounts.authority.key(),\n    ctx.accounts.{prog}_state.authority,\n    {prog.title()}Error::{errors[1]}\n);\n\n// Key inequality\nrequire_keys_neq!(\n    ctx.accounts.buyer.key(),\n    ctx.accounts.seller.key(),\n    {prog.title()}Error::{errors[2]}\n);\n\n// Numeric comparisons\nrequire_gt!(balance, min_amount, {prog.title()}Error::{errors[0]});\nrequire_gte!(balance, min_amount, {prog.title()}Error::{errors[0]});\nrequire_eq!(state, ExpectedState::Active, {prog.title()}Error::{errors[1]});\nrequire_neq!(state, ForbiddenState::Closed, {prog.title()}Error::{errors[2]});\n```",
        "require_macros"
    ))

# error propagation (5)
PROPAGATION = [
    ("map_err", "Convert SPL token errors", "token::transfer(cpi_ctx, amount).map_err(|_| error!(MyError::TransferFailed))?;"),
    ("into", "Convert with Into trait", "let result = some_operation().map_err(Into::<MyError>::into)?;"),
    ("from_trait", "Implement From for custom wrapping", "impl From<ProgramError> for MyError {\n    fn from(e: ProgramError) -> Self {\n        msg!(\"Program error: {:?}\", e);\n        MyError::ExternalProgramFailed\n    }\n}"),
    ("err_vs_error", "err!() vs error!()", "// error!() creates an AnchorError with file/line info\nreturn err!(MyError::Unauthorized);\n// Equivalent but adds source location:\nreturn Err(error!(MyError::Unauthorized));"),
    ("custom_msg", "Dynamic error messages", "msg!(\"Transfer failed: expected {} but got {}\", expected, actual);\nreturn err!(MyError::AmountMismatch);"),
]
for name, desc, code in PROPAGATION:
    records.append(make_rec(
        f"### Question\nHow do I {desc.lower()} in Anchor error handling?\n\n### Answer\n```rust\n{code}\n```\n\nKey points:\n- `err!()` returns `Err(AnchorError)` with source location\n- `error!()` creates an `AnchorError` you can return\n- Use `msg!()` to log context before returning errors\n- Custom error codes start at 6000 in Anchor",
        "error_propagation"
    ))

# ── 2. Common runtime errors (20 records) ──
RUNTIME_ERRORS = [
    ("AccountNotInitialized", "You're trying to read an account that hasn't been created yet.", "Ensure the account is initialized with `init` before accessing it. Check that the transaction includes the initialization instruction first."),
    ("InsufficientFunds", "The payer doesn't have enough SOL to cover rent + transaction fees.", "Check the payer's balance with `solana balance <address>`. The account needs enough SOL for rent-exemption (use `solana rent <bytes>` to check) plus transaction fees."),
    ("MissingRequiredSignature", "A required signer didn't sign the transaction.", "Ensure all accounts marked as `Signer<'info>` in your Accounts struct are included as signers in the client transaction. Check that `isSigner: true` is set in the client."),
    ("ConstraintMut", "An account that needs to be mutable wasn't marked as `#[account(mut)]`.", "Add `#[account(mut)]` to the account in your Accounts struct:\n```rust\n#[account(mut)]\npub my_account: Account<'info, MyData>,\n```"),
    ("ConstraintHasOne", "The `has_one` constraint failed — the account's field doesn't match.", "Check that the referenced account matches. For `#[account(has_one = authority)]`, the `authority` field in the account data must equal the `authority` account's key."),
    ("ConstraintSigner", "An account with `#[account(signer)]` constraint didn't sign.", "The account must be a transaction signer. In the client, include it in `signers: [...]`."),
    ("ConstraintSeeds", "PDA seeds don't match — the derived address doesn't equal the provided account.", "Verify your seeds match exactly between client and program:\n```rust\n// Program\n#[account(seeds = [b\"vault\", user.key().as_ref()], bump)]\n```\n```typescript\n// Client\nconst [vault] = PublicKey.findProgramAddressSync(\n  [Buffer.from(\"vault\"), user.toBuffer()],\n  programId\n);\n```"),
    ("ConstraintOwner", "Account is not owned by the expected program.", "Ensure the account was created by the correct program. SPL token accounts must be owned by the Token Program. Your program's accounts must be owned by your program ID."),
    ("ConstraintTokenMint", "Token account's mint doesn't match `token::mint` constraint.", "Verify the token account was created for the correct mint:\n```rust\n#[account(token::mint = mint, token::authority = authority)]\npub token_account: Account<'info, TokenAccount>,\n```"),
    ("ConstraintSpace", "Account data is too small for the struct.", "Increase space allocation. Calculate: `8 (discriminator) + struct fields`. Use `#[derive(InitSpace)]` for automatic calculation:\n```rust\n#[account(init, payer = user, space = 8 + MyStruct::INIT_SPACE)]\n```"),
    ("AccountDidNotDeserialize", "Account data doesn't match the expected struct layout.", "This usually means the account was created by a different program or has a different data layout. Check the account's owner program and data format."),
    ("AccountNotProgramOwned", "You're trying to deserialize an account not owned by your program.", "Use `Account<'info, T>` for accounts your program owns. Use `UncheckedAccount<'info>` or `AccountInfo<'info>` for external accounts (with manual checks)."),
    ("DeclaredProgramIdMismatch", "The program ID in `declare_program!` doesn't match the deployed address.", "Update your program ID:\n```rust\ndeclare_program!(\"YOUR_ACTUAL_PROGRAM_ID\");\n```\nGet your program ID with `solana address -k target/deploy/my_program-keypair.json`."),
    ("AccountBorrowFailed", "Two instructions in the same transaction are trying to mutably borrow the same account.", "Avoid using the same account mutably in multiple instructions within one transaction. Restructure to use a single instruction or separate transactions."),
    ("InvalidProgramId", "CPI is targeting the wrong program.", "Ensure you pass the correct program account for CPI:\n```rust\nlet cpi_program = ctx.accounts.token_program.to_account_info();\nlet cpi_ctx = CpiContext::new(cpi_program, transfer_accounts);\n```"),
    ("TransactionTooLarge", "Transaction exceeds the 1232-byte limit.", "Reduce the transaction size:\n- Use Address Lookup Tables for many accounts\n- Split into multiple transactions\n- Reduce instruction data size\n- Use versioned transactions (v0)"),
    ("BlockhashNotFound", "The recent blockhash has expired (older than ~60 seconds).", "Fetch a fresh blockhash before sending:\n```typescript\nconst { blockhash } = await connection.getLatestBlockhash();\ntx.recentBlockhash = blockhash;\n```\nOr use durable nonces for offline signing."),
    ("AlreadyProcessed", "This exact transaction was already processed.", "This is normal for retries. Check if the first attempt succeeded. If you need to resend, change the blockhash or add a unique nonce instruction."),
    ("InstructionError::Custom(0x1)", "Custom error code 0x1 (1) from a program.", "Convert hex error codes: `0x1` = 1. For Anchor programs, custom errors start at 6000. Check your `#[error_code]` enum. For SPL Token: error 1 = `InsufficientFunds`."),
    ("ProgramFailedToComplete", "Program ran out of compute units.", "Request more compute:\n```typescript\nconst modifyComputeUnits = ComputeBudgetProgram.setComputeUnitLimit({\n  units: 400_000\n});\ntx.add(modifyComputeUnits);\n```\nDefault is 200K CUs. Max is 1.4M per transaction."),
]
for err, cause, fix in RUNTIME_ERRORS:
    records.append(make_rec(
        f"### Question\nI'm getting `{err}` error in my Solana/Anchor program. What's wrong?\n\n### Answer\n**Cause:** {cause}\n\n**Fix:** {fix}",
        "runtime_errors"
    ))

# ── 3. Debugging techniques (15 records) ──
DEBUG_TECHNIQUES = [
    ("msg! macro", "How do I add debug logging in an Anchor program?",
     "Use the `msg!()` macro to log messages during program execution:\n\n```rust\npub fn transfer(ctx: Context<Transfer>, amount: u64) -> Result<()> {\n    msg!(\"Transfer: {} lamports from {} to {}\",\n        amount,\n        ctx.accounts.from.key(),\n        ctx.accounts.to.key()\n    );\n    // ... logic\n    msg!(\"Transfer complete. New balance: {}\", new_balance);\n    Ok(())\n}\n```\n\nView logs with `solana logs` or in transaction details on Explorer."),
    ("compute units", "How do I measure compute unit usage in my program?",
     "Use `sol_log_compute_units!()` to log remaining CUs:\n\n```rust\nuse anchor_lang::solana_program::log::sol_log_compute_units;\n\npub fn heavy_operation(ctx: Context<Heavy>) -> Result<()> {\n    sol_log_compute_units();  // Log CU before\n    // ... expensive operation\n    sol_log_compute_units();  // Log CU after\n    Ok(())\n}\n```\n\nThe difference tells you exactly how many CUs that section consumed."),
    ("solana logs", "How do I watch program logs in real-time?",
     "```bash\n# Watch all logs for your program\nsolana logs <PROGRAM_ID>\n\n# Watch logs on devnet\nsolana logs <PROGRAM_ID> --url devnet\n\n# Watch all transaction logs\nsolana logs --url localhost\n```\n\nLogs show `msg!()` output, CPI calls, error codes, and CU consumption."),
    ("anchor test", "How do I debug failing Anchor tests?",
     "```bash\n# Run tests with verbose output\nanchor test -- --verbose\n\n# Run a single test\nanchor test -- --grep \"test name\"\n\n# Keep validator running after tests\nanchor test --detach\n\n# Then inspect with solana CLI\nsolana logs <PROGRAM_ID> --url localhost\n```\n\nIn your test, log transaction signatures to inspect on Explorer:\n```typescript\nconsole.log(\"Tx:\", tx);\n```"),
    ("simulate", "How do I simulate a transaction without sending it?",
     "```typescript\n// Simulate to check for errors before sending\nconst simulation = await connection.simulateTransaction(tx);\nconsole.log(\"Logs:\", simulation.value.logs);\nconsole.log(\"Error:\", simulation.value.err);\nconsole.log(\"CU used:\", simulation.value.unitsConsumed);\n```\n\nSimulation runs the full transaction without committing state changes. Great for debugging and estimating compute."),
    ("anchor_toml", "What Anchor.toml settings help with debugging?",
     "```toml\n[features]\nseeds = true           # Enable automatic PDA seed verification\nskip-lint = false      # Keep linting on\n\n[test]\nstartup_wait = 10000   # Wait longer for validator startup (ms)\n\n[test.validator]\nurl = \"https://api.mainnet-beta.solana.com\"  # Fork mainnet state\n\n[[test.validator.clone]]\naddress = \"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA\"  # Clone programs\n```"),
    ("idl_fetch", "How do I inspect a deployed program's IDL?",
     "```bash\n# Fetch IDL from chain\nanchor idl fetch <PROGRAM_ID> --provider.cluster devnet\n\n# Decode an account using the IDL\nanchor account <ACCOUNT_TYPE> <ADDRESS> --provider.cluster devnet\n\n# Initialize IDL on chain (for others to fetch)\nanchor idl init <PROGRAM_ID> --filepath target/idl/my_program.json\n```"),
    ("account_inspect", "How do I inspect account data on-chain?",
     "```bash\n# View account info\nsolana account <ADDRESS>\n\n# View account data as base64\nsolana account <ADDRESS> --output json\n\n# Decode with Anchor\nanchor account MyStruct <ADDRESS>\n```\n\n```typescript\n// In TypeScript\nconst account = await program.account.myStruct.fetch(address);\nconsole.log(JSON.stringify(account, null, 2));\n```"),
    ("error_codes", "How do I decode Anchor error codes?",
     "Anchor error code ranges:\n- `0-99`: Framework internal errors\n- `100-4999`: Framework errors (e.g., 2001 = ConstraintMut)\n- `6000+`: Custom program errors (from your `#[error_code]` enum)\n\n```typescript\n// Decode in client\ntry {\n  await program.methods.myInstruction().rpc();\n} catch (e) {\n  if (e instanceof AnchorError) {\n    console.log(\"Error code:\", e.error.errorCode.number);\n    console.log(\"Error name:\", e.error.errorCode.code);\n    console.log(\"Message:\", e.error.errorMessage);\n  }\n}\n```"),
    ("priority_fees", "How do I debug 'transaction expired' errors?",
     "Transaction expiry usually means congestion. Add priority fees:\n\n```typescript\nimport { ComputeBudgetProgram } from '@solana/web3.js';\n\nconst priorityFee = ComputeBudgetProgram.setComputeUnitPrice({\n  microLamports: 50_000  // Adjust based on network congestion\n});\n\nconst computeLimit = ComputeBudgetProgram.setComputeUnitLimit({\n  units: 200_000\n});\n\ntx.add(priorityFee, computeLimit);\n```\n\nAlso use `skipPreflight: false` and check simulation results."),
    ("cpi_depth", "How do I debug CPI errors?",
     "Common CPI issues:\n\n1. **Max depth (4)**: You can only nest 4 levels of CPI calls\n2. **Missing accounts**: All accounts for the inner program must be passed through\n3. **Signer seeds**: PDA signers need `CpiContext::new_with_signer`\n\n```rust\n// Debug CPI by logging before/after\nmsg!(\"CPI to token program: transfer {} tokens\", amount);\ntoken::transfer(cpi_ctx, amount)?;\nmsg!(\"CPI transfer succeeded\");\n```\n\nIf CPI fails, the inner program's logs appear in the outer transaction logs."),
    ("account_size", "How do I debug 'account data too small' errors?",
     "Calculate required space:\n\n```rust\n#[account]\n#[derive(InitSpace)]\npub struct MyStruct {\n    pub authority: Pubkey,     // 32 bytes\n    #[max_len(50)]\n    pub name: String,          // 4 + 50 bytes\n    pub balance: u64,          // 8 bytes\n    pub items: Vec<u8>,        // 4 + len bytes\n    pub bump: u8,              // 1 byte\n}                              // Total: 8 (disc) + 32 + 54 + 8 + 4 + 1 = 107\n```\n\nUse `#[derive(InitSpace)]` with `#[max_len(N)]` for String/Vec. Space = 8 + MyStruct::INIT_SPACE."),
    ("clock_testing", "How do I test time-dependent logic?",
     "In bankrun tests, you can manipulate the clock:\n\n```typescript\nimport { start } from 'solana-bankrun';\n\nconst context = await start([], []);\nconst clock = await context.banksClient.getClock();\n\n// Fast-forward time\nclock.unixTimestamp = BigInt(Date.now() / 1000 + 86400); // +1 day\ncontext.setClock(clock);\n\n// Now test time-dependent logic\nawait context.banksClient.processTransaction(tx);\n```\n\nIn standard tests, use `solana_program::clock::Clock` sysvar."),
    ("log_parsing", "How do I parse program logs from a transaction?",
     "```typescript\nconst tx = await connection.getTransaction(signature, {\n  maxSupportedTransactionVersion: 0,\n});\n\n// All logs\nconsole.log(tx.meta.logMessages);\n\n// Filter for your program\nconst myLogs = tx.meta.logMessages.filter(log =>\n  log.includes('Program YOUR_PROGRAM_ID')\n);\n\n// Parse compute units\nconst cuLog = tx.meta.logMessages.find(log =>\n  log.includes('consumed')\n);\n```"),
    ("event_parsing", "How do I debug Anchor events?",
     "```rust\n#[event]\npub struct TradeEvent {\n    pub buyer: Pubkey,\n    pub seller: Pubkey,\n    pub price: u64,\n    pub timestamp: i64,\n}\n\n// Emit in instruction handler\nemit!(TradeEvent {\n    buyer: ctx.accounts.buyer.key(),\n    seller: ctx.accounts.seller.key(),\n    price: amount,\n    timestamp: Clock::get()?.unix_timestamp,\n});\n```\n\n```typescript\n// Listen in client\nprogram.addEventListener('TradeEvent', (event) => {\n  console.log('Trade:', event);\n});\n```"),
]
for name, q, a in DEBUG_TECHNIQUES:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "debugging"))

# ── 4. Common mistakes (20 records) ──
MISTAKES = [
    ("Forgetting #[account(mut)]", "Account is not marked mutable but the instruction modifies it.",
     "Add `#[account(mut)]` to any account that gets modified:\n```rust\n#[account(mut)]\npub user_account: Account<'info, UserData>,\n```"),
    ("Wrong PDA seeds order", "Seeds in the client don't match the program's seed order.",
     "Seeds must be in the exact same order:\n```rust\n// Program: seeds = [b\"pool\", mint.key().as_ref(), authority.key().as_ref()]\n// Client must match:\nconst [pda] = PublicKey.findProgramAddressSync(\n  [Buffer.from(\"pool\"), mint.toBuffer(), authority.toBuffer()],\n  programId\n);\n```"),
    ("Missing system_program", "Forgot to include system_program in accounts when using `init`.",
     "```rust\n#[derive(Accounts)]\npub struct Initialize<'info> {\n    #[account(mut)]\n    pub payer: Signer<'info>,\n    #[account(init, payer = payer, space = 8 + MyData::INIT_SPACE)]\n    pub data: Account<'info, MyData>,\n    pub system_program: Program<'info, System>,  // Required for init!\n}\n```"),
    ("Integer overflow", "Arithmetic operation overflows without checked math.",
     "Use checked arithmetic or Anchor's overflow protection:\n```rust\n// Bad: can overflow\nlet total = price * quantity;\n\n// Good: checked math\nlet total = price.checked_mul(quantity).ok_or(MyError::MathOverflow)?;\nlet new_balance = balance.checked_add(deposit).ok_or(MyError::MathOverflow)?;\nlet remaining = balance.checked_sub(withdrawal).ok_or(MyError::InsufficientFunds)?;\n```"),
    ("Wrong token program", "Using Token Program instead of Token-2022 (or vice versa).",
     "Check which token program the mint uses:\n```rust\n// For standard SPL tokens\npub token_program: Program<'info, Token>,\n\n// For Token-2022\npub token_program: Program<'info, Token2022>,\n\n// To support both — use Interface\nuse anchor_spl::token_interface::{TokenInterface, TokenAccount as ITokenAccount};\npub token_program: Interface<'info, TokenInterface>,\n```"),
    ("Pubkey comparison with ==", "Comparing Pubkeys incorrectly.",
     "Pubkey implements `PartialEq`, so `==` works. But for Anchor constraints, use `has_one` or `constraint`:\n```rust\n// Preferred: declarative\n#[account(has_one = authority)]\npub my_account: Account<'info, MyData>,\n\n// Also valid: explicit constraint\n#[account(constraint = my_account.authority == authority.key())]\npub my_account: Account<'info, MyData>,\n```"),
    ("Forgetting bump in PDA", "Not storing or using the bump seed.",
     "Always store the bump for later PDA verification:\n```rust\n#[account]\n#[derive(InitSpace)]\npub struct Vault {\n    pub authority: Pubkey,\n    pub bump: u8,  // Store the bump!\n}\n\n// On init:\nctx.accounts.vault.bump = ctx.bumps.vault;\n\n// For CPI signing:\nlet seeds = &[b\"vault\", authority.as_ref(), &[vault.bump]];\nlet signer = &[&seeds[..]];\nCpiContext::new_with_signer(program, accounts, signer)\n```"),
    ("Account size for String/Vec", "Not accounting for length prefix in String and Vec fields.",
     "String and Vec have a 4-byte length prefix:\n```rust\n#[account]\n#[derive(InitSpace)]\npub struct Profile {\n    pub name: String,    // 4 + max_len bytes\n    pub tags: Vec<u8>,   // 4 + (max_items * item_size) bytes\n}\n```\nUse `#[max_len(N)]` with InitSpace:\n```rust\n#[max_len(32)]\npub name: String,  // 4 + 32 = 36 bytes\n#[max_len(10)]\npub tags: Vec<u8>, // 4 + 10 = 14 bytes\n```"),
    ("Using i64 for amounts", "Using signed integers for token amounts.",
     "Token amounts should always be `u64` (unsigned):\n```rust\npub struct Vault {\n    pub balance: u64,      // ✅ Correct\n    pub total_staked: u64, // ✅ Correct\n    // pub balance: i64,   // ❌ Wrong — amounts can't be negative\n}\n```\nUse `i64` only for timestamps (from `Clock::get()?.unix_timestamp`)."),
    ("Not closing accounts", "Accounts are never closed, wasting rent.",
     "Close accounts when no longer needed to reclaim SOL:\n```rust\n#[derive(Accounts)]\npub struct CloseAccount<'info> {\n    #[account(mut, close = receiver, has_one = authority)]\n    pub my_account: Account<'info, MyData>,\n    pub authority: Signer<'info>,\n    #[account(mut)]\n    /// CHECK: receives rent\n    pub receiver: AccountInfo<'info>,\n}\n```\nThe `close` constraint zeros data, transfers lamports, and assigns to system program."),
    ("Hardcoded program IDs", "Hardcoding program IDs instead of using constants.",
     "Use well-known constants:\n```rust\nuse anchor_spl::token::ID as TOKEN_PROGRAM_ID;\nuse anchor_spl::associated_token::ID as ATA_PROGRAM_ID;\n\n// Or in Accounts struct — Anchor validates automatically:\npub token_program: Program<'info, Token>,\npub associated_token_program: Program<'info, AssociatedToken>,\npub system_program: Program<'info, System>,\n```"),
    ("Unchecked accounts", "Using UncheckedAccount without proper validation.",
     "Always add `/// CHECK:` doc comment explaining why it's safe:\n```rust\n/// CHECK: This account is validated in the instruction handler\npub external_account: UncheckedAccount<'info>,\n```\n\nBetter: use specific types when possible:\n```rust\n// Instead of UncheckedAccount:\npub mint: Account<'info, Mint>,           // Validates owner + deserializes\npub token_acc: Account<'info, TokenAccount>, // Same\n```"),
    ("Rent exemption", "Not making accounts rent-exempt.",
     "All accounts should be rent-exempt. Anchor's `init` handles this automatically:\n```rust\n#[account(init, payer = user, space = 8 + MyData::INIT_SPACE)]\npub my_account: Account<'info, MyData>,\n```\n\nFor manual creation:\n```rust\nlet rent = Rent::get()?;\nlet lamports = rent.minimum_balance(data_len);\n```"),
    ("Cross-program authority", "Not verifying the authority for CPI calls.",
     "Always verify the signer has authority:\n```rust\n#[derive(Accounts)]\npub struct TransferTokens<'info> {\n    #[account(mut, token::authority = authority)]  // Verify authority\n    pub from: Account<'info, TokenAccount>,\n    #[account(mut)]\n    pub to: Account<'info, TokenAccount>,\n    pub authority: Signer<'info>,  // Must sign\n    pub token_program: Program<'info, Token>,\n}\n```"),
    ("Anchor version mismatch", "Using patterns from the wrong Anchor version.",
     "Modern Anchor 0.30+ uses:\n```rust\n// ✅ Modern (0.30+)\nuse anchor_lang::prelude::*;\n\n#[account]\n#[derive(InitSpace)]\npub struct MyData { ... }\n\n// Access bumps via ctx.bumps.account_name\nlet bump = ctx.bumps.vault;\n```\n\n```toml\n# Cargo.toml — use solana-foundation\n[dependencies]\nanchor-lang = \"0.30.1\"\n```\n\nAvoid old patterns: `declare_id!()`, `coral-xyz/anchor`, `ctx.bumps.get(\"name\")`."),
    ("Account order in client", "Passing accounts in wrong order in the client.",
     "Anchor clients handle ordering automatically:\n```typescript\n// ✅ Correct — use named accounts\nawait program.methods\n  .initialize()\n  .accounts({\n    userAccount: userPda,\n    authority: wallet.publicKey,\n    systemProgram: SystemProgram.programId,\n  })\n  .rpc();\n\n// Anchor resolves the correct order from the IDL.\n// Don't manually construct AccountMeta arrays unless necessary.\n```"),
    ("Stale oracle prices", "Using oracle prices without checking staleness.",
     "Always validate oracle data freshness:\n```rust\nuse pyth_solana_receiver_sdk::price_update::PriceUpdateV2;\n\nlet price_update = &ctx.accounts.price_feed;\nlet price = price_update.get_price_no_older_than(\n    &Clock::get()?,\n    60,  // Max age in seconds\n    &feed_id,\n)?;\n\nlet price_value = price.price;\nlet confidence = price.conf;\nrequire!(confidence < price_value.unsigned_abs() / 100, MyError::PriceUncertain);\n```"),
    ("Missing rent sysvar", "Passing rent sysvar when it's not needed in modern Solana.",
     "Modern Solana (1.17+) doesn't require explicit rent sysvar:\n```rust\n// ❌ Old pattern — unnecessary\npub rent: Sysvar<'info, Rent>,\n\n// ✅ Modern — get rent programmatically\nlet rent = Rent::get()?;\n\n// Anchor's init constraint handles rent automatically.\n// You almost never need to pass the rent sysvar.\n```"),
    ("Vec without max_len", "Using Vec in account struct without specifying max length.",
     "Always use `#[max_len(N)]` with Vec and String:\n```rust\n#[account]\n#[derive(InitSpace)]\npub struct GameState {\n    #[max_len(100)]\n    pub players: Vec<Pubkey>,  // 4 + (100 * 32) = 3,204 bytes\n    #[max_len(50)]\n    pub name: String,          // 4 + 50 = 54 bytes\n}\n```\n\nWithout `max_len`, InitSpace can't calculate size and compilation fails."),
    ("Decimal precision", "Using floating point for financial calculations.",
     "Never use f32/f64 on Solana — they're deterministic but lose precision:\n```rust\n// ❌ Bad: floating point\nlet fee = amount as f64 * 0.025;\n\n// ✅ Good: basis points (1 bp = 0.01%)\nlet fee_bps: u16 = 250; // 2.5%\nlet fee = amount\n    .checked_mul(fee_bps as u64).ok_or(MyError::Overflow)?\n    .checked_div(10_000).ok_or(MyError::Overflow)?;\n```"),
]
for title, cause, fix in MISTAKES:
    records.append(make_rec(
        f"### Question\nWhat's wrong with this Anchor code? Common mistake: {title}\n\n### Answer\n**Problem:** {cause}\n\n**Fix:**\n{fix}",
        "common_mistakes"
    ))

# ── 5. Compute budget (10 records) ──
COMPUTE = [
    ("default CU limit", "What's the default compute unit limit on Solana?", "200,000 CU per instruction, 1,400,000 CU max per transaction. Request more with `ComputeBudgetProgram.setComputeUnitLimit()`."),
    ("request more CU", "How do I request more compute units?", "```typescript\nimport { ComputeBudgetProgram } from '@solana/web3.js';\n\ntx.add(\n  ComputeBudgetProgram.setComputeUnitLimit({ units: 400_000 }),\n  ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 1_000 })\n);\n```"),
    ("CU optimization: borsh", "How do I reduce compute usage for serialization?", "Use `zero_copy` for large accounts to avoid Borsh serialization:\n```rust\n#[account(zero_copy)]\n#[repr(C)]\npub struct LargeState {\n    pub data: [u64; 1000],  // Read directly from memory, no deserialization\n}\n```"),
    ("CU optimization: references", "How do I reduce compute by avoiding clones?", "Use references instead of cloning:\n```rust\n// ❌ Wastes CU\nlet key = ctx.accounts.user.key().clone();\n\n// ✅ Use reference\nlet key = ctx.accounts.user.key();\n// Or borrow\nlet key_ref = &ctx.accounts.user.key();\n```"),
    ("CU optimization: stack", "How do I avoid stack overflow in programs?", "Solana stack limit is 4KB. For large structs:\n```rust\n// Move large data to heap\nlet data = Box::new(LargeStruct::default());\n\n// Or use zero_copy accounts (read from account memory directly)\n#[account(zero_copy)]\npub struct LargeState { ... }\n```"),
    ("measure CU", "How do I measure exact CU usage of my instructions?", "```typescript\nconst sim = await connection.simulateTransaction(tx);\nconsole.log('CU consumed:', sim.value.unitsConsumed);\n```\n\nIn program:\n```rust\nuse solana_program::log::sol_log_compute_units;\nsol_log_compute_units(); // Logs remaining CU\n```"),
    ("CU costs: syscalls", "What are the CU costs of common operations?", "Approximate CU costs:\n- SHA256 hash: ~100 CU per 32 bytes\n- Ed25519 verify: ~2,000 CU\n- CPI call: ~1,000 CU overhead\n- Account create: ~5,000 CU\n- Borsh serialize: varies by size\n- Log (msg!): ~100 CU per call\n\nUse `sol_log_compute_units()` to measure precisely."),
    ("CU and priority fees", "How do priority fees relate to compute units?", "Priority fee = microLamports per CU. Total priority fee = CU_limit × price_per_CU.\n\n```typescript\n// 200K CU at 1000 microLamports/CU = 0.2 SOL * 10^-6 * 1000 = 0.0002 SOL\nComputeBudgetProgram.setComputeUnitLimit({ units: 200_000 })\nComputeBudgetProgram.setComputeUnitPrice({ microLamports: 1_000 })\n```\n\nSet CU limit as low as possible to save on fees."),
    ("CU optimization: math", "How do I optimize math operations for CU?", "```rust\n// Prefer bit shifts over division by powers of 2\nlet half = amount >> 1;  // Instead of amount / 2\n\n// Use unchecked math only when overflow is impossible\nlet idx = i as usize;  // If i is validated to be < array.len()\n\n// Pre-compute constants\nconst DENOMINATOR: u64 = 10_000;\nlet fee = amount * fee_bps / DENOMINATOR;\n```"),
    ("CU budget per ix", "Can different instructions in a transaction have different CU limits?", "No — `setComputeUnitLimit` applies to the entire transaction, shared across all instructions. Plan accordingly:\n\n```typescript\n// If you have 3 instructions, each needing ~100K CU\ntx.add(\n  ComputeBudgetProgram.setComputeUnitLimit({ units: 350_000 }), // Some buffer\n  instruction1,\n  instruction2,\n  instruction3,\n);\n```"),
]
for name, q, a in COMPUTE:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "compute_budget"))

# ── Write output ──
PROCESSED.mkdir(parents=True, exist_ok=True)
out = PROCESSED / "synthetic-bulk7.jsonl"
with open(out, "w") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"Wrote {len(records)} records to {out}")
cats = {}
for r in records:
    c = r["metadata"]["category"]
    cats[c] = cats.get(c, 0) + 1
for c, n in sorted(cats.items()):
    print(f"  {c}: {n}")
