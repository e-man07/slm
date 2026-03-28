#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 10: Solana runtime concepts.
Target: ~150 records.
"""
import hashlib, json
from pathlib import Path

PROCESSED = Path(__file__).parent.parent / "data" / "processed"

def make_rec(content, category, lang="rust"):
    return {
        "id": hashlib.sha256(content.encode()).hexdigest(),
        "source": "synthetic/glan", "source_type": "synthetic",
        "content": content, "language": lang, "license": "synthetic-original",
        "metadata": {"method": "glan", "category": category, "anchor_version_class": "modern"},
    }

records = []

# ── 1. Account model (15) ──
ACCOUNT_TOPICS = [
    ("ownership", "Who owns accounts on Solana?",
     "Every account has an `owner` program. Only the owner program can modify the account's data and debit lamports.\n\n- System Program owns all wallet accounts\n- Token Program owns all token accounts\n- Your program owns accounts it creates\n\n```rust\n// Anchor verifies ownership automatically:\npub my_data: Account<'info, MyStruct>,  // Checks owner == your program ID\npub token_acc: Account<'info, TokenAccount>,  // Checks owner == Token Program\n```"),
    ("rent_exemption", "How does rent exemption work on Solana?",
     "Accounts must maintain a minimum SOL balance to avoid being garbage collected:\n\n```rust\nlet rent = Rent::get()?;\nlet min_balance = rent.minimum_balance(data_len);\n// ~0.00089 SOL per byte per year\n// 128 bytes ≈ 0.00113 SOL for rent-exemption\n```\n\nAnchor's `init` constraint automatically ensures rent-exemption. Accounts below the threshold are collected after ~2 years."),
    ("data_layout", "What's the layout of an Anchor account?",
     "```\n[8 bytes: discriminator][N bytes: struct data]\n```\n\nThe 8-byte discriminator is SHA256(\"account:StructName\")[:8]. It prevents type confusion attacks.\n\n```rust\n#[account]\n#[derive(InitSpace)]\npub struct MyData {\n    pub authority: Pubkey,  // 32 bytes\n    pub value: u64,         // 8 bytes\n    pub bump: u8,           // 1 byte\n}  // Total space: 8 + 32 + 8 + 1 = 49 bytes\n```"),
    ("lamports", "How do lamports work?",
     "1 SOL = 1,000,000,000 lamports (10^9). All SOL amounts in programs use lamports.\n\n```rust\n// Check balance\nlet balance = ctx.accounts.user.lamports();\n\n// Transfer lamports between program-owned accounts\n**ctx.accounts.from.to_account_info().try_borrow_mut_lamports()? -= amount;\n**ctx.accounts.to.to_account_info().try_borrow_mut_lamports()? += amount;\n\n// For non-program-owned accounts, use system_program::transfer\n```"),
    ("executable", "What makes an account executable on Solana?",
     "Programs are stored in executable accounts. Key properties:\n- `executable: true` flag set by the BPF Loader\n- Program data is stored in a separate data account (upgradeable loader)\n- Programs have a program authority that can upgrade them\n\n```bash\n# Check if an account is a program\nsolana account <ADDRESS> | grep executable\n\n# Make a program immutable (permanently non-upgradeable)\nsolana program set-upgrade-authority <PROGRAM_ID> --final\n```"),
    ("pda_vs_keypair", "What's the difference between PDAs and keypair accounts?",
     "**Keypair accounts:** Created by generating a cryptographic keypair. The private key can sign transactions.\n\n**PDAs (Program Derived Addresses):** Derived deterministically from seeds + program ID. No private key exists — only the program can \"sign\" for them via `invoke_signed`.\n\n```rust\n// PDA: deterministic, program-controlled\n#[account(\n    seeds = [b\"vault\", user.key().as_ref()],\n    bump,\n)]\npub vault: Account<'info, Vault>,\n\n// Keypair: random, user-controlled\npub user: Signer<'info>,\n```\n\nUse PDAs for program-owned state. Use keypairs for user wallets."),
    ("max_size", "What's the maximum account size on Solana?",
     "**10 MB** (10,485,760 bytes). But practical limits:\n- Accounts > 10KB should use `zero_copy` to avoid CU costs\n- Initial allocation is fixed — use `realloc` to grow later\n- Cost: ~0.007 SOL per KB for rent-exemption\n\n```rust\n#[account(zero_copy)]\n#[repr(C)]\npub struct LargeData {\n    pub items: [u64; 1000],  // 8KB — use zero_copy\n}\n```"),
    ("account_types", "What account types does Anchor provide?",
     "```rust\n// Your program's accounts\nAccount<'info, T>        // Deserialized, owner-checked\nAccountLoader<'info, T>  // Zero-copy, lazy deserialization\n\n// System accounts\nSigner<'info>            // Must sign the transaction\nSystemAccount<'info>     // SOL wallet (system-owned)\n\n// SPL accounts\nAccount<'info, TokenAccount>  // Token account\nAccount<'info, Mint>          // Token mint\n\n// Program references\nProgram<'info, System>   // System program\nProgram<'info, Token>    // Token program\n\n// Unchecked (use sparingly)\nUncheckedAccount<'info>  // No validation\nAccountInfo<'info>       // Raw account info\n```"),
    ("account_discriminator", "How does Anchor prevent account type confusion?",
     "Every Anchor account has an 8-byte discriminator (first 8 bytes of SHA256(\"account:TypeName\")):\n\n```rust\n#[account]\npub struct Vault { ... }    // discriminator: sha256(\"account:Vault\")[:8]\n#[account]\npub struct Config { ... }   // discriminator: sha256(\"account:Config\")[:8]\n```\n\nWhen you use `Account<'info, Vault>`, Anchor checks the discriminator matches. This prevents:\n- Passing a Config account where a Vault is expected\n- Passing accounts from other programs"),
    ("account_lifecycle", "What's the lifecycle of a Solana account?",
     "1. **Create**: `init` allocates space, pays rent, sets owner\n2. **Use**: Read/write data, transfer tokens\n3. **Resize**: `realloc` to grow/shrink (must pay/refund rent difference)\n4. **Close**: Zero data, transfer lamports, assign to System Program\n\n```rust\n// Create\n#[account(init, payer = user, space = 8 + MyData::INIT_SPACE)]\npub data: Account<'info, MyData>,\n\n// Resize\n#[account(mut, realloc = 8 + new_size, realloc::payer = user, realloc::zero = false)]\npub data: Account<'info, MyData>,\n\n// Close\n#[account(mut, close = user)]\npub data: Account<'info, MyData>,\n```"),
]
for name, q, a in ACCOUNT_TOPICS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "account_model"))

# More account topics
ACCOUNT_EXTRA = [
    ("sysvar", "What are sysvars on Solana?",
     "Sysvars are special read-only accounts providing cluster state:\n\n```rust\nlet clock = Clock::get()?;           // Current slot, timestamp, epoch\nlet rent = Rent::get()?;             // Rent parameters\nlet epoch_schedule = EpochSchedule::get()?;\n\n// In Accounts struct (if you need the AccountInfo):\npub clock: Sysvar<'info, Clock>,\n\n// Common sysvars:\n// Clock: timestamp, slot, epoch\n// Rent: lamport cost per byte\n// EpochSchedule: epoch timing\n// Instructions: current transaction's instructions\n// SlotHashes: recent slot hashes\n```"),
    ("account_close_attack", "What is the account close/revival attack?",
     "If you close an account (zero data + transfer lamports) but another instruction in the same transaction re-funds it, the account data could be garbage.\n\n**Anchor handles this** by setting the discriminator to a special \"closed\" value, so any attempt to use the account after closing will fail deserialization.\n\n```rust\n// Safe with Anchor:\n#[account(mut, close = user)]\npub data: Account<'info, MyData>,\n// Anchor writes CLOSED_ACCOUNT_DISCRIMINATOR\n```"),
    ("type_cosplay", "What is a type cosplay attack?",
     "An attacker creates an account with the same data layout as another type, hoping the program accepts it.\n\n**Anchor prevents this** with the 8-byte discriminator. Each account type has a unique discriminator prefix.\n\n```rust\n// Both Vault and Config might have similar fields,\n// but their discriminators differ:\n// Vault:  [56, 12, 34, ...]\n// Config: [78, 90, 12, ...]\n// Anchor checks discriminator on every Account<'info, T> access.\n```"),
    ("reinitialization", "What is a reinitialization attack?",
     "An attacker re-initializes an already-initialized account, overwriting existing data.\n\n**Anchor's `init` constraint prevents this** — it checks the discriminator is zeroed (uninitialized). If the account already has a discriminator, init fails.\n\n```rust\n// Safe: Anchor checks account isn't already initialized\n#[account(init, payer = user, space = 8 + MyData::INIT_SPACE)]\npub data: Account<'info, MyData>,\n```"),
    ("owner_check", "Why are owner checks important?",
     "Without owner checks, an attacker could pass an account they own that has the right data layout.\n\n```rust\n// Anchor does owner checks automatically:\npub data: Account<'info, MyData>,  // Checks owner == your program ID\n\n// Manual check (for AccountInfo):\nrequire!(\n    *account.owner == expected_program_id,\n    MyError::InvalidOwner\n);\n```"),
]
for name, q, a in ACCOUNT_EXTRA:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "account_model"))

# ── 2. Transaction processing (15) ──
TX_TOPICS = [
    ("lifecycle", "What's the lifecycle of a Solana transaction?",
     "1. **Build**: Create instructions, set accounts, add recent blockhash\n2. **Sign**: All required signers sign the transaction\n3. **Send**: RPC node receives and forwards via Gulf Stream\n4. **Process**: Leader validator executes instructions sequentially\n5. **Confirm**: Validators vote, reaching confirmation thresholds\n6. **Finalize**: ~32 slots later, transaction is finalized\n\nAll instructions in a transaction execute atomically — all succeed or all fail."),
    ("fees", "How are transaction fees calculated on Solana?",
     "```\nTotal fee = Base fee + Priority fee\nBase fee = 5000 lamports per signature (0.000005 SOL)\nPriority fee = Compute units × Price per CU (microLamports)\n```\n\n```typescript\n// Add priority fee\ntx.add(\n  ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 1000 }),\n  ComputeBudgetProgram.setComputeUnitLimit({ units: 200000 }),\n);\n// Fee: 5000 + (200000 × 1000 / 1e6) = 5000 + 200 = 5200 lamports\n```\n\n50% of priority fees are burned, 50% go to the validator."),
    ("versioned", "What are versioned transactions?",
     "Versioned transactions (v0) support Address Lookup Tables (ALTs) to reference more accounts:\n\n- **Legacy**: Max ~35 accounts (limited by 1232-byte tx size)\n- **v0**: Up to 256 accounts using ALTs (only 32-byte table address instead of 32 bytes per account)\n\nUse v0 when your transaction needs many accounts (e.g., DEX swaps, complex DeFi)."),
    ("blockhash", "How do recent blockhashes work?",
     "Every transaction includes a `recent_blockhash` for:\n1. **Deduplication**: Same tx can't be processed twice\n2. **Expiry**: Blockhash expires after ~60 seconds (~150 slots)\n\n```typescript\nconst { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash();\ntx.recentBlockhash = blockhash;\n\n// For offline/delayed signing, use durable nonces instead\n```"),
    ("compute_units", "How do compute units work?",
     "- Default: 200,000 CU per instruction\n- Max: 1,400,000 CU per transaction\n- Each operation costs CUs (syscalls, math, memory, CPI)\n- Unused CUs are NOT refunded but don't cost priority fees if you set limit correctly\n\n```rust\n// In program: log remaining CU\nuse solana_program::log::sol_log_compute_units;\nsol_log_compute_units();\n```"),
    ("parallel_execution", "How does Solana achieve parallel transaction execution?",
     "**Sealevel** executes non-conflicting transactions in parallel:\n- Transactions declare all accounts upfront\n- Read-only accounts: unlimited parallel access\n- Writable accounts: exclusive access (serialized)\n\nDesign implications:\n- Minimize shared writable state\n- Use per-user PDAs instead of global counters\n- Split hot accounts into shards"),
    ("instruction_format", "What's inside a Solana instruction?",
     "```rust\npub struct Instruction {\n    pub program_id: Pubkey,      // Which program to call\n    pub accounts: Vec<AccountMeta>, // Accounts to pass\n    pub data: Vec<u8>,           // Instruction data (serialized args)\n}\n\npub struct AccountMeta {\n    pub pubkey: Pubkey,\n    pub is_signer: bool,\n    pub is_writable: bool,\n}\n```\n\nAnchor serializes instruction data using Borsh with an 8-byte discriminator (SHA256(\"global:instruction_name\")[:8])."),
    ("alt", "How do Address Lookup Tables work?",
     "ALTs store up to 256 addresses in a single on-chain account. Transactions reference addresses by index (1 byte) instead of full pubkey (32 bytes).\n\n```typescript\n// Create ALT\nconst [createIx, lookupTableAddress] = AddressLookupTableProgram.createLookupTable({\n  authority: payer.publicKey,\n  payer: payer.publicKey,\n  recentSlot: await connection.getSlot(),\n});\n\n// Extend with addresses\nconst extendIx = AddressLookupTableProgram.extendLookupTable({\n  lookupTable: lookupTableAddress,\n  authority: payer.publicKey,\n  payer: payer.publicKey,\n  addresses: [addr1, addr2, addr3],\n});\n```"),
    ("inner_instructions", "What are inner instructions?",
     "Inner instructions are CPI calls made by programs during execution. They appear in transaction metadata:\n\n```typescript\nconst tx = await connection.getTransaction(sig, {\n  maxSupportedTransactionVersion: 0,\n});\n\n// Inner instructions grouped by outer instruction index\nfor (const inner of tx.meta.innerInstructions) {\n  console.log(`Outer ix ${inner.index}:`);\n  for (const ix of inner.instructions) {\n    console.log(`  CPI to program index ${ix.programIdIndex}`);\n  }\n}\n```"),
    ("nonce_accounts", "What are durable transaction nonces?",
     "Nonce accounts replace `recent_blockhash` for transactions that need to be signed offline or over long periods:\n\n1. Create nonce account with `SystemProgram.nonceInitialize`\n2. Use the nonce value as `recentBlockhash`\n3. First instruction must be `nonceAdvance`\n4. Transaction never expires (until nonce is advanced)\n\nUse cases: multi-sig workflows, hardware wallet signing, scheduled transactions."),
]
for name, q, a in TX_TOPICS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "transaction_processing", "md"))

# More tx topics
TX_EXTRA = [
    ("max_accounts", "How many accounts can a transaction have?", "64 accounts per transaction in legacy, 256 with v0 + Address Lookup Tables. Each account adds 32 bytes (legacy) or 1 byte (ALT reference) to the transaction."),
    ("max_ix_data", "What's the max instruction data size?", "Transaction total size limit is 1232 bytes. This includes signatures, header, account keys, blockhash, and all instruction data. Typical max instruction data is ~800-900 bytes after overhead."),
    ("tx_size", "How do I reduce transaction size?", "1. Use Address Lookup Tables (v0 transactions)\n2. Minimize instruction data\n3. Split into multiple transactions\n4. Use compact encoding for arrays\n5. Avoid passing unnecessary accounts"),
    ("confirmation_times", "How long does transaction confirmation take?", "- **Processed**: ~400ms (leader processed it)\n- **Confirmed**: ~5 seconds (supermajority voted)\n- **Finalized**: ~12 seconds (~32 slots after confirmed)\n\nFor most applications, `confirmed` is sufficient."),
    ("tx_priority", "How do priority fees affect transaction ordering?", "Validators order transactions by priority fee per compute unit. Higher fee = processed sooner during congestion.\n\nTypical fees:\n- Low congestion: 1-100 microLamports/CU\n- Medium: 100-10,000 microLamports/CU\n- High congestion: 10,000-1,000,000 microLamports/CU"),
]
for name, q, a in TX_EXTRA:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "transaction_processing", "md"))

# ── 3. Program runtime (10) ──
RUNTIME = [
    ("stack_limit", "What's the stack size limit for Solana programs?", "4KB. For large local variables, use `Box::new()` to allocate on the heap (32KB). Deeply recursive functions can overflow the stack."),
    ("heap_limit", "What's the heap size for Solana programs?", "32KB default. Request more with `sol_alloc_free` or by using the custom heap allocator.\n\n```rust\n// Custom heap size (in program entrypoint)\n#[global_allocator]\nstatic ALLOC: solana_program::entrypoint::BumpAllocator = \n    solana_program::entrypoint::BumpAllocator { start: 0, len: 64 * 1024 }; // 64KB\n```"),
    ("cpi_depth_limit", "What's the CPI depth limit?", "4 levels of nesting. Your program is level 0 when called by the runtime. Each CPI increases depth by 1. At depth 4, any CPI call will fail."),
    ("max_ix_accounts", "How many accounts can one instruction reference?", "256 accounts per instruction (since Solana 1.17). Previously was 35. This is separate from the transaction-level limit."),
    ("instruction_introspection", "Can a program see other instructions in the transaction?", "Yes, via the Instructions sysvar:\n\n```rust\nuse solana_program::sysvar::instructions;\n\nlet ix = instructions::get_instruction_relative(0, &ix_sysvar)?; // Current\nlet prev = instructions::get_instruction_relative(-1, &ix_sysvar)?; // Previous\nlet next = instructions::get_instruction_relative(1, &ix_sysvar)?; // Next\n```\n\nUseful for flash loan verification, multi-step protocols, and sandwich attack prevention."),
    ("bpf_sbf", "What's the difference between BPF and SBF?", "**BPF** (Berkeley Packet Filter): Original Solana program format.\n**SBF** (Solana Binary Format): Current format, based on eBPF with Solana-specific extensions.\n\nFor developers, the difference is transparent — `cargo build-sbf` compiles your Rust to SBF. The runtime handles both formats."),
    ("program_cache", "How does program caching work?", "Solana caches compiled programs in memory. First call to a program in an epoch incurs JIT compilation cost. Subsequent calls use the cached version.\n\nImplication: First transactions after a program deploy may use slightly more CU."),
    ("log_limits", "What are the logging limits in Solana programs?", "- `msg!()` output is truncated at 10KB per transaction\n- Each `msg!()` call costs ~100 CU\n- Logs are only visible in transaction metadata, not stored on-chain\n- Use sparingly in production to save CU"),
    ("return_data", "How does return data work between programs?", "Programs can set up to 1024 bytes of return data:\n\n```rust\nuse solana_program::program::set_return_data;\nset_return_data(&price.to_le_bytes());\n\n// Caller retrieves:\nuse solana_program::program::get_return_data;\nlet (program_id, data) = get_return_data().unwrap();\n```\n\nReturn data is cleared when the next CPI is made."),
    ("cross_program_invocation", "How does CPI work internally?", "1. Calling program builds an `Instruction` with program_id, accounts, data\n2. Runtime verifies all accounts are passed to the calling program\n3. Runtime checks CPI depth < 4\n4. Runtime invokes the target program with the provided accounts\n5. If target fails, the entire transaction fails (atomic)\n6. Signer privileges can be escalated via `invoke_signed` (PDA signing)"),
]
for name, q, a in RUNTIME:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "program_runtime", "md"))

# ── 4. Security concepts (15) ──
SECURITY = [
    ("signer_check", "Why are signer checks critical?",
     "Without signer checks, anyone can call your instruction and pretend to be the authority:\n\n```rust\n// ✅ Anchor handles this with Signer type:\npub authority: Signer<'info>,  // Must sign the transaction\n\n// ✅ Combined with has_one:\n#[account(has_one = authority)]\npub vault: Account<'info, Vault>,\npub authority: Signer<'info>,\n\n// ❌ VULNERABLE — no signer check:\n/// CHECK: unchecked\npub authority: AccountInfo<'info>,  // Anyone can pass any pubkey!\n```"),
    ("owner_check", "Why do owner checks matter?",
     "Without owner checks, an attacker can pass an account from a different program with crafted data:\n\n```rust\n// ✅ Anchor checks owner automatically:\npub data: Account<'info, MyStruct>,  // owner must be your program\n\n// ❌ VULNERABLE:\n/// CHECK: no owner check\npub data: AccountInfo<'info>,\n// Attacker creates account with same data layout but different program\n```"),
    ("pda_authority", "How do PDAs provide authority?",
     "PDAs have no private key — only the deriving program can sign for them via `invoke_signed`. This makes them secure authority accounts:\n\n```rust\n// The vault PDA can only be \"signed\" by your program\nlet seeds = &[b\"vault\", pool.key().as_ref(), &[vault.bump]];\nlet signer = &[&seeds[..]];\n\n// Only YOUR program can make this CPI with the vault as signer\ntoken::transfer(\n    CpiContext::new_with_signer(token_program, accounts, signer),\n    amount,\n)?;\n```"),
    ("arithmetic_overflow", "How do I prevent arithmetic overflow?",
     "```rust\n// ❌ VULNERABLE — can overflow silently\nlet total = price * quantity;\n\n// ✅ SAFE — returns None on overflow\nlet total = price.checked_mul(quantity).ok_or(MyError::Overflow)?;\nlet sum = a.checked_add(b).ok_or(MyError::Overflow)?;\nlet diff = a.checked_sub(b).ok_or(MyError::Underflow)?;\nlet ratio = a.checked_div(b).ok_or(MyError::DivByZero)?;\n\n// Also safe: Rust's default overflow checks in debug mode\n// But in release mode (on-chain), overflow wraps silently!\n// Always use checked_ methods.\n```"),
    ("reentrancy", "Is reentrancy possible on Solana?",
     "**No.** Solana prevents reentrancy by design:\n1. A program cannot CPI back into itself\n2. The runtime tracks the call stack and rejects circular calls\n3. CPI depth is limited to 4 levels\n\nThis is fundamentally different from Ethereum. **Do not suggest reentrancy guards** — they are unnecessary and misleading on Solana."),
    ("float_determinism", "Are floating point operations deterministic on Solana?",
     "**Yes.** Solana uses software-emulated floats via LLVM, making them deterministic across all validators. However, floats still have precision issues:\n\n```rust\n// ✅ Deterministic but imprecise:\nlet ratio = amount as f64 / total as f64;\n\n// ✅ Better — use fixed-point:\nlet ratio_bps = amount.checked_mul(10_000)?.checked_div(total)?;\n\n// Use integer math with basis points for financial calculations.\n```"),
    ("missing_account_check", "What happens if I forget to validate an account?",
     "The program might operate on wrong data. Example: a user passes someone else's token account.\n\n```rust\n// ❌ No validation — any token account works:\n/// CHECK: unchecked\npub token_account: AccountInfo<'info>,\n\n// ✅ Validated — must be the correct mint and owner:\n#[account(\n    mut,\n    token::mint = mint,\n    token::authority = user,\n)]\npub token_account: Account<'info, TokenAccount>,\n```"),
    ("front_running", "How do I protect against front-running on Solana?",
     "Solana's continuous block production makes front-running harder but not impossible:\n\n```rust\n// Use slippage protection for swaps\nrequire!(\n    output_amount >= min_output_amount,\n    MyError::SlippageExceeded\n);\n\n// Use commit-reveal for auctions/games\n// Phase 1: User commits hash(bid + nonce)\n// Phase 2: User reveals bid + nonce, program verifies\n\n// Use expiry timestamps\nrequire!(\n    Clock::get()?.unix_timestamp <= order.expiry,\n    MyError::OrderExpired\n);\n```"),
    ("sandwich_protection", "How do I prevent sandwich attacks?",
     "```rust\n// 1. Slippage bounds\nrequire!(amount_out >= min_amount_out, MyError::SlippageExceeded);\n\n// 2. Instruction introspection — reject if suspicious programs in tx\nlet ixs = &ctx.accounts.instruction_sysvar;\nlet num_ixs = instructions::load_current_index_checked(ixs)?;\n// Check no other DEX program calls in the same transaction\n\n// 3. Use Jito bundles for atomic execution without mempool exposure\n```"),
    ("deprecated_apis", "What deprecated Solana APIs should I avoid?",
     "- `declare_id!()` → Use `declare_program!()` (Anchor 0.30+)\n- `coral-xyz/anchor` → Use `solana-foundation/anchor`\n- `ctx.bumps.get(\"name\")` → Use `ctx.bumps.name`\n- `load_instruction_at()` → Use `get_instruction_relative()`\n- `#[state]` → Removed in modern Anchor\n- `Rent` sysvar as account → Use `Rent::get()?`"),
]
for name, q, a in SECURITY:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "security"))

SECURITY_EXTRA = [
    ("access_control", "How do I implement role-based access control?",
     "```rust\n#[account]\n#[derive(InitSpace)]\npub struct Config {\n    pub admin: Pubkey,\n    pub operator: Pubkey,\n    pub paused: bool,\n}\n\n// Admin-only instruction\n#[derive(Accounts)]\npub struct AdminAction<'info> {\n    #[account(has_one = admin)]\n    pub config: Account<'info, Config>,\n    pub admin: Signer<'info>,\n}\n\n// Operator instruction\n#[derive(Accounts)]\npub struct OperatorAction<'info> {\n    #[account(has_one = operator, constraint = !config.paused @ MyError::Paused)]\n    pub config: Account<'info, Config>,\n    pub operator: Signer<'info>,\n}\n```"),
    ("input_validation", "What input validation should I always do?",
     "```rust\npub fn process(ctx: Context<Process>, amount: u64, name: String) -> Result<()> {\n    // Validate amounts\n    require!(amount > 0, MyError::ZeroAmount);\n    require!(amount <= MAX_AMOUNT, MyError::AmountTooLarge);\n    \n    // Validate strings\n    require!(name.len() <= 32, MyError::NameTooLong);\n    require!(!name.is_empty(), MyError::EmptyName);\n    \n    // Validate timestamps\n    let clock = Clock::get()?;\n    require!(expiry > clock.unix_timestamp, MyError::AlreadyExpired);\n    \n    // Validate percentages\n    require!(fee_bps <= 10_000, MyError::InvalidFee); // Max 100%\n    \n    Ok(())\n}\n```"),
    ("emergency_pause", "How do I implement an emergency pause?",
     "```rust\n#[account]\npub struct GlobalState {\n    pub authority: Pubkey,\n    pub paused: bool,\n}\n\n// Add to every user-facing instruction:\n#[derive(Accounts)]\npub struct UserAction<'info> {\n    #[account(constraint = !global.paused @ MyError::ProtocolPaused)]\n    pub global: Account<'info, GlobalState>,\n    // ...\n}\n\n// Admin-only pause toggle:\npub fn set_paused(ctx: Context<AdminOnly>, paused: bool) -> Result<()> {\n    ctx.accounts.global.paused = paused;\n    msg!(\"Protocol paused: {}\", paused);\n    Ok(())\n}\n```"),
    ("upgrade_authority", "How do I manage program upgrade security?",
     "```bash\n# Check current authority\nsolana program show <PROGRAM_ID>\n\n# Transfer upgrade authority\nsolana program set-upgrade-authority <PROGRAM_ID> --new-upgrade-authority <NEW_KEY>\n\n# Make immutable (IRREVERSIBLE)\nsolana program set-upgrade-authority <PROGRAM_ID> --final\n\n# Use multisig for upgrade authority in production\n# Consider timelock for upgrades (governance vote → delay → execute)\n```"),
    ("audit_checklist", "What should I check in a Solana security audit?",
     "1. **Signer checks**: Every privileged action requires appropriate signer\n2. **Owner checks**: All deserialized accounts verified for correct owner\n3. **PDA validation**: Seeds match expected derivation\n4. **Arithmetic**: All math uses checked operations\n5. **Account close**: Proper cleanup, no revival attacks\n6. **Access control**: Admin functions properly gated\n7. **Input validation**: Bounds checking on all user inputs\n8. **CPI safety**: Correct program IDs, proper signer seeds\n9. **Reinitialization**: Can't re-init existing accounts\n10. **Token operations**: Correct mint/authority constraints"),
]
for name, q, a in SECURITY_EXTRA:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "security"))

# ── 5. Performance optimization (15) ──
PERF = [
    ("zero_copy", "When should I use zero-copy accounts?",
     "Use zero-copy for accounts > 1KB to avoid expensive Borsh deserialization:\n\n```rust\n#[account(zero_copy)]\n#[repr(C)]  // Required for zero-copy\npub struct OrderBook {\n    pub bids: [Order; 100],  // Large fixed-size array\n    pub asks: [Order; 100],\n    pub count: u32,\n}\n\n#[zero_copy]\n#[repr(C)]\npub struct Order {\n    pub price: u64,\n    pub quantity: u64,\n    pub owner: Pubkey,\n}\n\n// Access:\nlet loader = &ctx.accounts.order_book;\nlet book = loader.load()?;     // Immutable\nlet book = loader.load_mut()?; // Mutable\n```\n\nTradeoffs: No String/Vec (fixed-size only), alignment restrictions, more complex code."),
    ("batch_operations", "How do I batch operations efficiently?",
     "```rust\n// ❌ Slow: loop with CPI per iteration\nfor user in users {\n    token::transfer(ctx, amount)?;  // CPI overhead each time\n}\n\n// ✅ Fast: batch state changes, single CPI\nlet total = amount.checked_mul(users.len() as u64)?;\ntoken::transfer(ctx, total)?;  // One CPI\n\n// Update multiple records in one instruction\npub fn batch_update(ctx: Context<BatchUpdate>, updates: Vec<(u32, u64)>) -> Result<()> {\n    let data = &mut ctx.accounts.state.load_mut()?;\n    for (idx, value) in updates {\n        data.values[idx as usize] = value;\n    }\n    Ok(())\n}\n```"),
    ("minimize_accounts", "How do I minimize account reads?",
     "Each account access costs CU. Minimize by:\n\n```rust\n// ❌ Two account reads\nlet balance = ctx.accounts.vault.amount;\nlet authority = ctx.accounts.vault.authority;\n\n// ✅ One read, reuse reference\nlet vault = &ctx.accounts.vault;\nlet balance = vault.amount;\nlet authority = vault.authority;\n\n// For zero-copy: load once\nlet data = ctx.accounts.state.load()?;\nlet x = data.field_a;  // No additional IO\nlet y = data.field_b;\n```"),
    ("pack_state", "How do I pack state efficiently?",
     "```rust\n// ❌ Wasted space\npub struct Wasteful {\n    pub is_active: bool,  // 1 byte but uses 8 with alignment\n    pub balance: u64,     // 8 bytes\n    pub is_frozen: bool,  // 1 byte\n}\n\n// ✅ Pack booleans into a single u8\npub struct Efficient {\n    pub balance: u64,\n    pub flags: u8,  // bit 0 = active, bit 1 = frozen, etc.\n}\n\nimpl Efficient {\n    pub fn is_active(&self) -> bool { self.flags & 1 != 0 }\n    pub fn is_frozen(&self) -> bool { self.flags & 2 != 0 }\n    pub fn set_active(&mut self, v: bool) {\n        if v { self.flags |= 1 } else { self.flags &= !1 }\n    }\n}\n```"),
    ("reduce_cpi", "How do I reduce CPI overhead?",
     "Each CPI costs ~1000 CU overhead. Combine operations:\n\n```rust\n// ❌ 3 CPIs\ntoken::transfer(ctx_a, fee)?;\ntoken::transfer(ctx_b, deposit)?;\ntoken::mint_to(ctx_c, reward)?;\n\n// ✅ Calculate net amounts, fewer CPIs\nlet net_deposit = amount - fee;\ntoken::transfer(ctx_fee, fee)?;\ntoken::transfer(ctx_deposit, net_deposit)?;\n// Mint rewards in a separate batch instruction\n```"),
]
for name, q, a in PERF:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "performance"))

# ── 6. Staking, Clock, Native Programs (fill remaining ~30) ──
NATIVE_PROGRAMS = [
    ("system_program", "What does the System Program do?",
     "The System Program (11111111111111111111111111111111) manages:\n- Creating new accounts\n- Transferring SOL\n- Allocating account space\n- Assigning account ownership\n\nEvery new account starts owned by the System Program until assigned to another program."),
    ("token_program", "What's the difference between Token Program and Token-2022?",
     "**Token Program** (TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA):\n- Original SPL token standard\n- Simple, battle-tested\n- No extensions\n\n**Token-2022** (TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb):\n- Transfer hooks, fees, confidential transfers\n- Metadata on mint\n- Non-transferable tokens\n- CPI guard\n\nUse Token-2022 for new projects needing extensions. Use original for maximum compatibility."),
    ("associated_token", "What does the Associated Token Program do?",
     "Creates deterministic token account addresses:\n\n```\nATA = findProgramAddress(\n  [owner, TOKEN_PROGRAM_ID, mint],\n  ASSOCIATED_TOKEN_PROGRAM_ID\n)\n```\n\nEvery (wallet, mint) pair has exactly one ATA. This eliminates the need to track token account addresses."),
    ("bpf_loader", "What is the BPF Loader?",
     "The BPF Loader deploys and manages programs:\n- **BPF Loader 2** (Upgradeable): Current default, supports upgrades\n- Stores program data in a separate buffer account\n- Upgrade authority can update the program code\n- Can be made immutable by removing upgrade authority"),
    ("config_program", "What is the Config Program?",
     "Stores simple configuration data on-chain. Rarely used directly — most programs manage their own config accounts. Used internally by the validator for feature flags."),
    ("compute_budget", "What is the Compute Budget Program?",
     "Sets compute limits and priority fees:\n\n```typescript\n// Request more CU\nComputeBudgetProgram.setComputeUnitLimit({ units: 400_000 })\n\n// Set priority fee\nComputeBudgetProgram.setComputeUnitPrice({ microLamports: 1000 })\n\n// Request heap size\nComputeBudgetProgram.requestHeapFrame({ bytes: 64 * 1024 })\n```"),
    ("address_lookup_table", "What is the Address Lookup Table Program?",
     "Manages lookup tables for versioned transactions. Allows referencing up to 256 addresses by index instead of full pubkey, dramatically reducing transaction size for complex operations."),
]
for name, q, a in NATIVE_PROGRAMS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "native_programs", "md"))

CLOCK_TOPICS = [
    ("clock_sysvar", "How do I get the current time in a Solana program?",
     "```rust\nlet clock = Clock::get()?;\nlet timestamp = clock.unix_timestamp;  // i64, seconds since epoch\nlet slot = clock.slot;                 // Current slot number\nlet epoch = clock.epoch;               // Current epoch\n```\n\n**Warning:** `unix_timestamp` is an estimate based on validator votes. It can drift ~1-2 seconds. Don't use for sub-second precision."),
    ("time_pitfalls", "What are common pitfalls with time on Solana?",
     "1. **Clock drift**: Timestamps can be off by 1-2 seconds\n2. **Slot duration**: ~400ms average but varies\n3. **Testing**: Use bankrun's `setClock()` for time-dependent tests\n4. **Time zones**: Always use UTC (unix_timestamp is UTC)\n\n```rust\n// ❌ Don't assume exact slot times\nlet time_diff = (current_slot - start_slot) * 400; // Unreliable\n\n// ✅ Use unix_timestamp for time calculations\nlet elapsed = clock.unix_timestamp - start_timestamp;\nrequire!(elapsed >= COOLDOWN_SECONDS, MyError::CooldownActive);\n```"),
    ("epoch_schedule", "How do Solana epochs work?",
     "An epoch is ~2-3 days (~432,000 slots):\n- Validator stake changes take effect at epoch boundaries\n- Leader schedule is computed per epoch\n- Inflation rewards are distributed per epoch\n\n```rust\nlet epoch_schedule = EpochSchedule::get()?;\nlet slots_per_epoch = epoch_schedule.slots_per_epoch;\nlet current_epoch = Clock::get()?.epoch;\n```"),
]
for name, q, a in CLOCK_TOPICS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "clock_time", "md"))

# Syscalls
SYSCALLS = [
    ("sha256", "How do I hash data in a Solana program?",
     "```rust\nuse anchor_lang::solana_program::hash;\n\nlet data = b\"hello world\";\nlet hash = hash::hash(data);\nmsg!(\"Hash: {}\", hash);\n```\n\nCost: ~100 CU per 32 bytes. For Keccak256 (Ethereum compatibility):\n```rust\nuse anchor_lang::solana_program::keccak;\nlet hash = keccak::hash(data);\n```"),
    ("ed25519_verify", "How do I verify an Ed25519 signature in a program?",
     "Use the Ed25519 precompile via instruction introspection:\n\n```rust\n// The Ed25519 signature verification must be a separate instruction\n// in the same transaction (not a CPI).\n// Your program reads the Instructions sysvar to verify it happened.\n\nuse anchor_lang::solana_program::ed25519_program;\nuse anchor_lang::solana_program::sysvar::instructions;\n\n// Verify an Ed25519 verify instruction exists before our instruction\nlet ix = instructions::get_instruction_relative(-1, &ix_sysvar)?;\nrequire!(ix.program_id == ed25519_program::ID, MyError::MissingVerification);\n```"),
    ("secp256k1", "How do I recover a secp256k1 signature (Ethereum compatibility)?",
     "```rust\nuse anchor_lang::solana_program::secp256k1_recover::secp256k1_recover;\n\nlet recovered_pubkey = secp256k1_recover(\n    &message_hash,\n    recovery_id,\n    &signature,\n)?;\n// Compare with expected Ethereum address\n```\n\nThis is useful for cross-chain verification (e.g., verifying Ethereum signatures on Solana)."),
]
for name, q, a in SYSCALLS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "syscalls"))

# ── Write output ──
PROCESSED.mkdir(parents=True, exist_ok=True)
out = PROCESSED / "synthetic-bulk10.jsonl"
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
