#!/usr/bin/env python3
"""Generate adversarial refusal and correction SFT training examples.

Produces examples that teach the model to REFUSE deprecated patterns and provide
modern Solana/Anchor alternatives. Also generates DPO pairs (chosen=correct
refusal, rejected=deprecated code).

Usage:
    python scripts/gen_adversarial_sft.py
    python scripts/gen_adversarial_sft.py --out-dir data/processed
"""
from __future__ import annotations

import itertools
import json
import random
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from schema import Record, today_str, write_jsonl

app = typer.Typer(help="Generate adversarial refusal SFT + DPO examples.")
console = Console()

DATA_DIR = Path("data/processed")

SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns "
    "(solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! — these are deprecated."
)

# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------
# Each category has:
#   scenarios  — concrete program types / use cases
#   phrasings  — ways a user might ask the question
#   correct_response_fn — callable(scenario, phrasing) -> str  (assistant reply)
#   rejected_response_fn — callable(scenario, phrasing) -> str  (deprecated reply)
#   target_count — desired example count (we sample from cross-product)
# ---------------------------------------------------------------------------


# ======================================================================
# 1. REENTRANCY GUARDS
# ======================================================================

REENTRANCY_SCENARIOS = [
    ("staking program", "users stake SOL and earn rewards"),
    ("token vault", "users deposit and withdraw SPL tokens"),
    ("DEX / AMM", "a decentralized exchange with swap and liquidity functions"),
    ("lending protocol", "users supply collateral and borrow tokens"),
    ("escrow program", "two parties exchange tokens atomically"),
    ("DAO treasury", "governance-controlled treasury that disburses funds"),
    ("NFT marketplace", "buyers and sellers trade NFTs with royalties"),
    ("cross-program router", "a program that routes CPI calls across multiple protocols"),
]

REENTRANCY_PHRASINGS = [
    "My {scenario} is vulnerable to reentrancy attacks. How do I add a reentrancy guard?",
    "Write a reentrancy protection wrapper for my {scenario}.",
    "I need a mutex lock to prevent reentrancy in my {scenario}. Show me how.",
    "How do I implement a ReentrancyGuard struct for my Solana {scenario}?",
    "Is my {scenario} ({desc}) safe from reentrancy? Should I add a lock?",
    "Show me how to protect my {scenario} from cross-program reentrancy exploits.",
    "I'm porting an EVM {scenario} to Solana. How do I translate the reentrancy guard?",
    "Can you add an is_locked boolean field to prevent reentrancy in my {scenario}?",
    "Write a safe version of my {scenario} with reentrancy protection.",
    "What's the best pattern to prevent reentrancy attacks in a Solana {scenario}?",
]


def _reentrancy_correct(scenario: str, desc: str, phrasing: str) -> str:
    responses = [
        (
            f"Solana does **not** need reentrancy guards. Unlike the EVM, the Solana runtime "
            f"enforces a maximum CPI depth of 4, and accounts are locked (borrow-checked) during "
            f"cross-program invocations. This makes reentrancy impossible at the protocol level.\n\n"
            f"For your {scenario} ({desc}), focus on the security checks that actually matter:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n\n"
            f"#[derive(Accounts)]\n"
            f"pub struct SecureAction<'info> {{\n"
            f"    #[account(mut, has_one = authority @ ErrorCode::Unauthorized)]\n"
            f"    pub state: Account<'info, ProgramState>,\n"
            f"    pub authority: Signer<'info>,\n"
            f"}}\n\n"
            f"pub fn secure_action(ctx: Context<SecureAction>, amount: u64) -> Result<()> {{\n"
            f"    require!(amount > 0, ErrorCode::InvalidAmount);\n"
            f"    let state = &mut ctx.accounts.state;\n"
            f"    state.total = state.total.checked_add(amount)\n"
            f"        .ok_or(ErrorCode::Overflow)?;\n"
            f"    Ok(())\n"
            f"}}\n"
            f"```\n\n"
            f"Key Solana security patterns: signer validation, ownership checks (`has_one`), "
            f"checked arithmetic, and PDA seed constraints."
        ),
        (
            f"Reentrancy guards are unnecessary on Solana. The runtime prevents reentrancy "
            f"through two mechanisms:\n"
            f"1. **CPI depth limit** — maximum 4 levels of cross-program invocation\n"
            f"2. **Account borrow checker** — an account cannot be mutably borrowed by two "
            f"programs simultaneously\n\n"
            f"For your {scenario}, instead of a mutex/lock pattern, implement proper Anchor "
            f"constraints:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n\n"
            f"#[derive(Accounts)]\n"
            f"pub struct Withdraw<'info> {{\n"
            f"    #[account(\n"
            f"        mut,\n"
            f"        seeds = [b\"vault\", authority.key().as_ref()],\n"
            f"        bump = vault.bump,\n"
            f"        has_one = authority,\n"
            f"    )]\n"
            f"    pub vault: Account<'info, Vault>,\n"
            f"    #[account(mut)]\n"
            f"    pub authority: Signer<'info>,\n"
            f"    pub system_program: Program<'info, System>,\n"
            f"}}\n"
            f"```\n\n"
            f"This is safer than any lock-based approach because validation happens before "
            f"execution, and the runtime enforces account exclusivity."
        ),
        (
            f"You don't need a reentrancy guard for your {scenario}. This is an Ethereum "
            f"pattern that doesn't apply to Solana.\n\n"
            f"**Why Solana is reentrancy-safe:**\n"
            f"- The Solana runtime locks all accounts involved in a transaction\n"
            f"- CPI calls are limited to depth 4\n"
            f"- A program cannot call back into itself through CPI while it holds mutable "
            f"references to accounts\n\n"
            f"For {desc}, focus on:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n\n"
            f"// Use checked math — this IS a real Solana vulnerability\n"
            f"pub fn process(ctx: Context<Process>, amount: u64) -> Result<()> {{\n"
            f"    let balance = &mut ctx.accounts.account.balance;\n"
            f"    *balance = balance.checked_sub(amount)\n"
            f"        .ok_or(ErrorCode::InsufficientFunds)?;\n"
            f"    require_keys_eq!(\n"
            f"        ctx.accounts.account.owner,\n"
            f"        ctx.accounts.signer.key(),\n"
            f"        ErrorCode::Unauthorized\n"
            f"    );\n"
            f"    Ok(())\n"
            f"}}\n"
            f"```"
        ),
    ]
    return random.choice(responses)


def _reentrancy_rejected(scenario: str, desc: str, phrasing: str) -> str:
    return (
        f"You're right to worry about reentrancy in your {scenario}. Here's a reentrancy "
        f"guard pattern:\n\n"
        f"```rust\n"
        f"use anchor_lang::prelude::*;\n\n"
        f"#[account]\n"
        f"pub struct ReentrancyGuard {{\n"
        f"    pub is_locked: bool,\n"
        f"}}\n\n"
        f"pub fn guarded_action(ctx: Context<GuardedAction>) -> Result<()> {{\n"
        f"    let guard = &mut ctx.accounts.reentrancy_guard;\n"
        f"    require!(!guard.is_locked, ErrorCode::ReentrancyDetected);\n"
        f"    guard.is_locked = true;\n"
        f"    // ... your logic here ...\n"
        f"    guard.is_locked = false;\n"
        f"    Ok(())\n"
        f"}}\n"
        f"```\n\n"
        f"This lock flag prevents reentrancy attacks by ensuring the function cannot be "
        f"called again while it's executing."
    )


# ======================================================================
# 2. declare_id!
# ======================================================================

DECLARE_ID_SCENARIOS = [
    ("new Anchor project", "starting a fresh Anchor program"),
    ("migrating from Anchor 0.28", "upgrading an existing program"),
    ("multi-program workspace", "workspace with several programs"),
    ("program with IDL", "program that needs on-chain IDL"),
    ("verifiable build", "program that needs deterministic builds"),
    ("deployed mainnet program", "updating a live program"),
]

DECLARE_ID_PHRASINGS = [
    "How do I use declare_id! in my {scenario}?",
    "Show me how to set the program ID with declare_id! in Anchor.",
    "My {scenario} needs a program ID. Should I use declare_id!?",
    "Add declare_id! to this Anchor program:\nuse anchor_lang::prelude::*;\n\n#[program]\nmod my_program {{ }}",
    "What's the correct way to declare my program ID in Anchor 0.30+?",
    "I'm {desc}. Do I still need declare_id! for the program address?",
    "Generate the boilerplate for a new Anchor program with declare_id!.",
    "Is declare_id! required in modern Anchor programs?",
    "Show me the Anchor program template with declare_id! macro.",
    "How do I specify which address my program deploys to in Anchor?",
]


def _declare_id_correct(scenario: str, desc: str, phrasing: str) -> str:
    responses = [
        (
            f"`declare_id!` is deprecated in Anchor 0.30+. Modern Anchor programs use the "
            f"`#[program]` attribute, which reads the program ID from `Anchor.toml` and "
            f"`target/deploy/<name>-keypair.json` automatically.\n\n"
            f"For your {scenario}:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n\n"
            f"#[program]\n"
            f"pub mod my_program {{\n"
            f"    use super::*;\n\n"
            f"    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {{\n"
            f"        Ok(())\n"
            f"    }}\n"
            f"}}\n"
            f"```\n\n"
            f"The program ID is configured in `Anchor.toml`:\n"
            f"```toml\n"
            f"[programs.localnet]\n"
            f"my_program = \"YOUR_PROGRAM_ID\"\n"
            f"```\n\n"
            f"Run `anchor keys list` to see your program's public key."
        ),
        (
            f"The `declare_id!` macro is no longer needed in Anchor 0.30+. The `#[program]` "
            f"attribute handles program ID binding automatically.\n\n"
            f"Here is the modern template:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n\n"
            f"#[program]\n"
            f"pub mod my_program {{\n"
            f"    use super::*;\n\n"
            f"    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {{\n"
            f"        msg!(\"Program initialized\");\n"
            f"        Ok(())\n"
            f"    }}\n"
            f"}}\n\n"
            f"#[derive(Accounts)]\n"
            f"pub struct Initialize {{}}\n"
            f"```\n\n"
            f"Your program address comes from the deploy keypair. Set it in `Anchor.toml` "
            f"under `[programs.localnet]`."
        ),
        (
            f"No, you should not use `declare_id!` — it was removed in Anchor 0.30. "
            f"Modern Anchor derives the program ID from `Anchor.toml` and the deploy keypair.\n\n"
            f"For {desc}, your program file should look like:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n\n"
            f"#[program]\n"
            f"pub mod my_program {{\n"
            f"    use super::*;\n\n"
            f"    pub fn initialize(ctx: Context<Initialize>, data: u64) -> Result<()> {{\n"
            f"        ctx.accounts.state.value = data;\n"
            f"        Ok(())\n"
            f"    }}\n"
            f"}}\n"
            f"```\n\n"
            f"No `declare_id!` needed. The toolchain handles it."
        ),
    ]
    return random.choice(responses)


def _declare_id_rejected(scenario: str, desc: str, phrasing: str) -> str:
    return (
        f"Here's how to use `declare_id!` in your Anchor program:\n\n"
        f"```rust\n"
        f"use anchor_lang::prelude::*;\n\n"
        f"declare_id!(\"YourProgramPubkeyHere11111111111111111111111\");\n\n"
        f"#[program]\n"
        f"pub mod my_program {{\n"
        f"    use super::*;\n\n"
        f"    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {{\n"
        f"        Ok(())\n"
        f"    }}\n"
        f"}}\n"
        f"```\n\n"
        f"Replace the string with your actual program ID from `solana address -k "
        f"target/deploy/my_program-keypair.json`."
    )


# ======================================================================
# 3. coral-xyz/anchor
# ======================================================================

CORAL_SCENARIOS = [
    ("Cargo.toml dependency", "adding anchor-lang to Cargo.toml"),
    ("GitHub reference", "linking to Anchor source code"),
    ("documentation link", "referencing Anchor docs or examples"),
    ("CI/CD pipeline", "setting up build and test automation"),
    ("project template", "scaffolding a new Anchor workspace"),
]

CORAL_PHRASINGS = [
    "What's the correct GitHub repo for Anchor? Is it coral-xyz/anchor?",
    "Show me the Cargo.toml for an Anchor project using coral-xyz/anchor.",
    "I'm {desc}. Should I reference coral-xyz/anchor?",
    "Where do I find the Anchor framework source code?",
    "Write a Cargo.toml with anchor-lang from the coral-xyz organization.",
    "What GitHub org maintains Anchor now?",
    "I'm setting up my {scenario}. Which Anchor repo should I use?",
    "Show me how to add Anchor as a git dependency from coral-xyz/anchor.",
    "Is coral-xyz/anchor still the right repo for Anchor development?",
    "Help me configure my {scenario} with the correct Anchor dependency.",
]


def _coral_correct(scenario: str, desc: str, phrasing: str) -> str:
    responses = [
        (
            f"The Anchor framework has moved from `coral-xyz/anchor` to "
            f"`solana-foundation/anchor`. The old repo is unmaintained.\n\n"
            f"For your {scenario}:\n\n"
            f"```toml\n"
            f"# Cargo.toml\n"
            f"[dependencies]\n"
            f"anchor-lang = \"0.30.1\"\n"
            f"anchor-spl = \"0.30.1\"\n"
            f"```\n\n"
            f"The crates on crates.io are published from `solana-foundation/anchor`. "
            f"You typically don't need a git dependency — just use the crate version.\n\n"
            f"GitHub: https://github.com/solana-foundation/anchor"
        ),
        (
            f"No, `coral-xyz/anchor` is deprecated. Anchor is now maintained by the Solana "
            f"Foundation at `solana-foundation/anchor`.\n\n"
            f"Use the crates.io dependency (no git reference needed):\n\n"
            f"```toml\n"
            f"[dependencies]\n"
            f"anchor-lang = \"0.30.1\"\n"
            f"```\n\n"
            f"If you need the repo for issues, examples, or source:\n"
            f"https://github.com/solana-foundation/anchor"
        ),
        (
            f"The correct repository is **solana-foundation/anchor**, not `coral-xyz/anchor`. "
            f"The project moved to the Solana Foundation organization.\n\n"
            f"For {desc}:\n\n"
            f"```toml\n"
            f"[dependencies]\n"
            f"anchor-lang = \"0.30.1\"\n"
            f"anchor-spl = \"0.30.1\"\n"
            f"\n"
            f"[dev-dependencies]\n"
            f"anchor-client = \"0.30.1\"\n"
            f"```\n\n"
            f"Install the CLI: `cargo install --git https://github.com/solana-foundation/anchor "
            f"--tag v0.30.1 anchor-cli`"
        ),
    ]
    return random.choice(responses)


def _coral_rejected(scenario: str, desc: str, phrasing: str) -> str:
    return (
        f"Yes, Anchor is maintained at `coral-xyz/anchor`. Here's the setup:\n\n"
        f"```toml\n"
        f"# Cargo.toml\n"
        f"[dependencies]\n"
        f"anchor-lang = {{ git = \"https://github.com/coral-xyz/anchor\", tag = \"v0.30.1\" }}\n"
        f"anchor-spl = {{ git = \"https://github.com/coral-xyz/anchor\", tag = \"v0.30.1\" }}\n"
        f"```\n\n"
        f"You can find examples and docs at https://github.com/coral-xyz/anchor."
    )


# ======================================================================
# 4. FLOAT ARITHMETIC
# ======================================================================

FLOAT_SCENARIOS = [
    ("token swap", "computing exchange rates between two tokens"),
    ("price oracle", "storing and computing token prices"),
    ("yield calculation", "calculating APY/APR for staking rewards"),
    ("fee computation", "computing protocol fees as percentages"),
    ("liquidity pool", "computing LP share ratios"),
    ("interest rate", "computing borrow/lend interest over time"),
    ("auction", "computing bid prices with fractional increments"),
    ("royalty split", "dividing NFT sale proceeds among creators"),
]

FLOAT_PHRASINGS = [
    "How do I calculate token prices using f64 in my {scenario}?",
    "Write a {scenario} that uses floating point for {desc}.",
    "Is it safe to use f32 for {desc} in a Solana program?",
    "Show me how to implement {desc} with float arithmetic on Solana.",
    "I need decimal precision for my {scenario}. Should I use f64?",
    "What data type should I use for {desc} in my Solana {scenario}?",
    "My {scenario} needs fractional amounts. Can I use floats?",
    "Implement a price calculation using float division in Solana.",
    "How do I handle decimal math for {desc} on-chain?",
    "Convert this EVM price calculation to Solana: `let price: f64 = amount as f64 / supply as f64;`",
]


def _float_correct(scenario: str, desc: str, phrasing: str) -> str:
    responses = [
        (
            f"**Never use `f32` or `f64` in Solana programs.** Floating-point arithmetic is "
            f"non-deterministic across different validator hardware, which means validators "
            f"could disagree on transaction results and fail to reach consensus.\n\n"
            f"For {desc} in your {scenario}, use fixed-point integer math:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n\n"
            f"// Use basis points (1 bp = 0.01%) for percentages\n"
            f"pub const BPS_DENOMINATOR: u64 = 10_000;\n\n"
            f"// Use u128 for intermediate calculations to avoid overflow\n"
            f"pub fn calculate_fee(amount: u64, fee_bps: u64) -> Result<u64> {{\n"
            f"    let fee = (amount as u128)\n"
            f"        .checked_mul(fee_bps as u128)\n"
            f"        .ok_or(ErrorCode::MathOverflow)?\n"
            f"        .checked_div(BPS_DENOMINATOR as u128)\n"
            f"        .ok_or(ErrorCode::MathOverflow)? as u64;\n"
            f"    Ok(fee)\n"
            f"}}\n"
            f"```\n\n"
            f"Common patterns: basis points (10000 = 100%), u128 scaled math, or "
            f"dedicated fixed-point libraries."
        ),
        (
            f"Floats (`f32`/`f64`) are forbidden in Solana programs. Floating-point results "
            f"vary across CPU architectures, breaking consensus.\n\n"
            f"For your {scenario}, use scaled integers:\n\n"
            f"```rust\n"
            f"// Price with 6 decimals of precision (like USDC)\n"
            f"pub const PRICE_SCALE: u64 = 1_000_000;\n\n"
            f"pub fn compute_output(\n"
            f"    input_amount: u64,\n"
            f"    price_scaled: u64, // e.g., 1_500_000 = $1.50\n"
            f") -> Result<u64> {{\n"
            f"    let output = (input_amount as u128)\n"
            f"        .checked_mul(price_scaled as u128)\n"
            f"        .ok_or(ErrorCode::Overflow)?\n"
            f"        .checked_div(PRICE_SCALE as u128)\n"
            f"        .ok_or(ErrorCode::Overflow)? as u64;\n"
            f"    Ok(output)\n"
            f"}}\n"
            f"```\n\n"
            f"Use `u64` for token amounts, `u128` for intermediate products, and basis "
            f"points or scaled denominators for fractions."
        ),
        (
            f"Do not use floating-point types for {desc}. On Solana, `f32` and `f64` produce "
            f"non-deterministic results across validators, which can cause consensus failures "
            f"and stuck transactions.\n\n"
            f"Here's the correct approach using integer math:\n\n"
            f"```rust\n"
            f"/// Calculate share of a pool: (user_deposit * total_shares) / total_deposits\n"
            f"pub fn calculate_share(\n"
            f"    user_deposit: u64,\n"
            f"    total_shares: u64,\n"
            f"    total_deposits: u64,\n"
            f") -> Result<u64> {{\n"
            f"    require!(total_deposits > 0, ErrorCode::EmptyPool);\n"
            f"    let share = (user_deposit as u128)\n"
            f"        .checked_mul(total_shares as u128)\n"
            f"        .ok_or(ErrorCode::Overflow)?\n"
            f"        .checked_div(total_deposits as u128)\n"
            f"        .ok_or(ErrorCode::Overflow)? as u64;\n"
            f"    Ok(share)\n"
            f"}}\n"
            f"```\n\n"
            f"For complex math (square roots, logarithms), use integer approximation "
            f"libraries or lookup tables."
        ),
    ]
    return random.choice(responses)


def _float_rejected(scenario: str, desc: str, phrasing: str) -> str:
    return (
        f"Here's how to use floating point for {desc} in your {scenario}:\n\n"
        f"```rust\n"
        f"pub fn calculate_price(amount: u64, supply: u64) -> f64 {{\n"
        f"    let price: f64 = amount as f64 / supply as f64;\n"
        f"    price\n"
        f"}}\n\n"
        f"pub fn calculate_fee(amount: u64, fee_percent: f64) -> u64 {{\n"
        f"    (amount as f64 * fee_percent) as u64\n"
        f"}}\n"
        f"```\n\n"
        f"Just cast between `u64` and `f64` as needed. Rust handles the conversion "
        f"automatically."
    )


# ======================================================================
# 5. load_instruction_at
# ======================================================================

LOAD_INSTR_SCENARIOS = [
    ("instruction introspection", "inspecting other instructions in a transaction"),
    ("flashloan guard", "verifying repayment instruction exists"),
    ("atomic check", "ensuring multiple instructions execute together"),
    ("CPI verification", "verifying the calling program"),
    ("composability check", "verifying transaction structure"),
]

LOAD_INSTR_PHRASINGS = [
    "How do I use load_instruction_at to inspect instructions in my Solana program?",
    "Show me how to verify the previous instruction using load_instruction_at.",
    "I need to check that a repayment instruction follows my borrow in a {scenario}.",
    "Write a {scenario} that reads other instructions in the transaction.",
    "Is load_instruction_at the right way to do {desc}?",
    "How do I introspect transaction instructions from within my {scenario}?",
    "Show me the Sysvar Instructions account pattern for {desc}.",
    "I want to verify the transaction contains a specific instruction for my {scenario}.",
]


def _load_instr_correct(scenario: str, desc: str, phrasing: str) -> str:
    responses = [
        (
            f"`load_instruction_at` is deprecated and has known security vulnerabilities — "
            f"it allows unvalidated instruction introspection that attackers can exploit.\n\n"
            f"For {desc}, use `get_instruction_relative` or validate through CPI context:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n"
            f"use solana_program::sysvar::instructions::{{self, get_instruction_relative}};\n\n"
            f"pub fn verify_instruction(\n"
            f"    ctx: Context<Verify>,\n"
            f") -> Result<()> {{\n"
            f"    let ix = get_instruction_relative(\n"
            f"        -1, // previous instruction\n"
            f"        &ctx.accounts.instructions,\n"
            f"    ).map_err(|_| ErrorCode::MissingInstruction)?;\n\n"
            f"    require_keys_eq!(\n"
            f"        ix.program_id,\n"
            f"        expected_program::ID,\n"
            f"        ErrorCode::InvalidProgram\n"
            f"    );\n"
            f"    Ok(())\n"
            f"}}\n\n"
            f"#[derive(Accounts)]\n"
            f"pub struct Verify<'info> {{\n"
            f"    /// CHECK: Sysvar instructions account\n"
            f"    #[account(address = instructions::ID)]\n"
            f"    pub instructions: AccountInfo<'info>,\n"
            f"}}\n"
            f"```\n\n"
            f"Always validate the `program_id` and data of introspected instructions."
        ),
        (
            f"Do not use `load_instruction_at` — it has been deprecated due to security "
            f"concerns. The function allows reading arbitrary transaction instructions without "
            f"proper bounds checking.\n\n"
            f"For your {scenario}, use the safer `get_instruction_relative`:\n\n"
            f"```rust\n"
            f"use solana_program::sysvar::instructions;\n\n"
            f"// Pass the Instructions sysvar account\n"
            f"#[derive(Accounts)]\n"
            f"pub struct CheckTx<'info> {{\n"
            f"    /// CHECK: validated by address constraint\n"
            f"    #[account(address = instructions::ID)]\n"
            f"    pub ix_sysvar: AccountInfo<'info>,\n"
            f"}}\n\n"
            f"pub fn check(ctx: Context<CheckTx>) -> Result<()> {{\n"
            f"    let next_ix = instructions::get_instruction_relative(\n"
            f"        1, &ctx.accounts.ix_sysvar\n"
            f"    ).map_err(|_| ErrorCode::NoFollowingInstruction)?;\n"
            f"    // Validate program_id and instruction data\n"
            f"    Ok(())\n"
            f"}}\n"
            f"```"
        ),
    ]
    return random.choice(responses)


def _load_instr_rejected(scenario: str, desc: str, phrasing: str) -> str:
    return (
        f"You can use `load_instruction_at` to inspect transaction instructions:\n\n"
        f"```rust\n"
        f"use solana_program::sysvar::instructions::load_instruction_at(\n"
        f"    0, // index of the instruction\n"
        f"    &ctx.accounts.instructions,\n"
        f");\n\n"
        f"let ix = load_instruction_at(0, &ctx.accounts.ix_account)?;\n"
        f"msg!(\"Program: {{}}\", ix.program_id);\n"
        f"```\n\n"
        f"Just pass the index of whichever instruction you want to read."
    )


# ======================================================================
# 6. CLOSED ACCOUNT DISCRIMINATOR
# ======================================================================

CLOSED_DISC_SCENARIOS = [
    ("account closing", "closing and reclaiming rent from accounts"),
    ("account revival attack", "preventing reuse of closed accounts"),
    ("garbage collection", "cleaning up stale program accounts"),
    ("rent reclamation", "returning SOL from unused accounts"),
    ("account lifecycle", "managing account creation and deletion"),
]

CLOSED_DISC_PHRASINGS = [
    "How do I check the closed account discriminator to prevent revival attacks?",
    "Show me how to set a discriminator on closed accounts in my {scenario}.",
    "I need to verify an account hasn't been closed and reopened in my {scenario}.",
    "Write a manual discriminator check for {desc} in Anchor.",
    "How do I prevent closed account attacks? Should I check the discriminator bytes?",
    "Is manually zeroing the discriminator necessary when closing accounts in Anchor?",
    "Show me the account closing pattern with discriminator protection for my {scenario}.",
    "How do I safely handle {desc} and prevent account reuse?",
]


def _closed_disc_correct(scenario: str, desc: str, phrasing: str) -> str:
    responses = [
        (
            f"You don't need to manually check discriminators for closed accounts. "
            f"Anchor's `close` constraint handles this automatically — it transfers lamports, "
            f"zeros account data, and sets the discriminator to a closed state.\n\n"
            f"For your {scenario}:\n\n"
            f"```rust\n"
            f"use anchor_lang::prelude::*;\n\n"
            f"#[derive(Accounts)]\n"
            f"pub struct CloseAccount<'info> {{\n"
            f"    #[account(\n"
            f"        mut,\n"
            f"        close = recipient,\n"
            f"        has_one = authority,\n"
            f"    )]\n"
            f"    pub account_to_close: Account<'info, MyAccount>,\n"
            f"    pub authority: Signer<'info>,\n"
            f"    /// CHECK: receives the rent\n"
            f"    #[account(mut)]\n"
            f"    pub recipient: AccountInfo<'info>,\n"
            f"}}\n"
            f"```\n\n"
            f"Anchor's `close` constraint:\n"
            f"1. Transfers all lamports to `recipient`\n"
            f"2. Zeros all account data\n"
            f"3. Sets the account discriminator to `CLOSED_ACCOUNT_DISCRIMINATOR`\n"
            f"4. On subsequent access attempts, Anchor rejects the account automatically\n\n"
            f"No manual discriminator manipulation needed."
        ),
        (
            f"Manual discriminator checking is an Ethereum-influenced pattern that Anchor "
            f"handles for you. The `close` constraint is the correct approach.\n\n"
            f"For {desc}:\n\n"
            f"```rust\n"
            f"#[derive(Accounts)]\n"
            f"pub struct Close<'info> {{\n"
            f"    #[account(mut, close = payer, has_one = payer)]\n"
            f"    pub data: Account<'info, DataAccount>,\n"
            f"    #[account(mut)]\n"
            f"    pub payer: Signer<'info>,\n"
            f"}}\n"
            f"```\n\n"
            f"When Anchor closes an account, it writes `CLOSED_ACCOUNT_DISCRIMINATOR` to "
            f"the first 8 bytes. Any future attempt to deserialize that account as a valid "
            f"Anchor account will fail with `AccountDiscriminatorMismatch`. You never need "
            f"to check this yourself."
        ),
        (
            f"Anchor already protects against closed account revival attacks. You do not "
            f"need manual discriminator checks.\n\n"
            f"Here's how account closing works in modern Anchor:\n\n"
            f"```rust\n"
            f"#[derive(Accounts)]\n"
            f"pub struct Cleanup<'info> {{\n"
            f"    #[account(\n"
            f"        mut,\n"
            f"        close = authority,\n"
            f"        constraint = account.is_expired() @ ErrorCode::NotExpired,\n"
            f"    )]\n"
            f"    pub account: Account<'info, TimedAccount>,\n"
            f"    #[account(mut)]\n"
            f"    pub authority: Signer<'info>,\n"
            f"}}\n"
            f"```\n\n"
            f"The `close` constraint handles rent reclamation, data zeroing, and "
            f"discriminator invalidation in one step. Any attempt to reuse the "
            f"account address will fail Anchor's deserialization check."
        ),
    ]
    return random.choice(responses)


def _closed_disc_rejected(scenario: str, desc: str, phrasing: str) -> str:
    return (
        f"To prevent closed account revival attacks, you need to manually check the "
        f"discriminator:\n\n"
        f"```rust\n"
        f"pub const CLOSED_DISCRIMINATOR: [u8; 8] = [0xFF; 8];\n\n"
        f"pub fn check_not_closed(account: &AccountInfo) -> Result<()> {{\n"
        f"    let data = account.data.borrow();\n"
        f"    let discriminator = &data[..8];\n"
        f"    if discriminator == &CLOSED_DISCRIMINATOR {{\n"
        f"        return Err(ErrorCode::AccountClosed.into());\n"
        f"    }}\n"
        f"    Ok(())\n"
        f"}}\n\n"
        f"pub fn close_account(account: &mut AccountInfo) {{\n"
        f"    let mut data = account.data.borrow_mut();\n"
        f"    data[..8].copy_from_slice(&CLOSED_DISCRIMINATOR);\n"
        f"    // Transfer lamports to recipient...\n"
        f"}}\n"
        f"```\n\n"
        f"Always check the discriminator before using any account to prevent "
        f"revival attacks."
    )


# ---------------------------------------------------------------------------
# Category registry
# ---------------------------------------------------------------------------

CATEGORIES = {
    "reentrancy": {
        "scenarios": REENTRANCY_SCENARIOS,
        "phrasings": REENTRANCY_PHRASINGS,
        "correct_fn": _reentrancy_correct,
        "rejected_fn": _reentrancy_rejected,
        "target_count": 50,
    },
    "declare_id": {
        "scenarios": DECLARE_ID_SCENARIOS,
        "phrasings": DECLARE_ID_PHRASINGS,
        "correct_fn": _declare_id_correct,
        "rejected_fn": _declare_id_rejected,
        "target_count": 50,
    },
    "coral_xyz": {
        "scenarios": CORAL_SCENARIOS,
        "phrasings": CORAL_PHRASINGS,
        "correct_fn": _coral_correct,
        "rejected_fn": _coral_rejected,
        "target_count": 40,
    },
    "floats": {
        "scenarios": FLOAT_SCENARIOS,
        "phrasings": FLOAT_PHRASINGS,
        "correct_fn": _float_correct,
        "rejected_fn": _float_rejected,
        "target_count": 50,
    },
    "load_instruction": {
        "scenarios": LOAD_INSTR_SCENARIOS,
        "phrasings": LOAD_INSTR_PHRASINGS,
        "correct_fn": _load_instr_correct,
        "rejected_fn": _load_instr_rejected,
        "target_count": 30,
    },
    "closed_discriminator": {
        "scenarios": CLOSED_DISC_SCENARIOS,
        "phrasings": CLOSED_DISC_PHRASINGS,
        "correct_fn": _closed_disc_correct,
        "rejected_fn": _closed_disc_rejected,
        "target_count": 30,
    },
}


# ---------------------------------------------------------------------------
# Generation logic
# ---------------------------------------------------------------------------


def _build_messages(user_msg: str, assistant_msg: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": assistant_msg},
    ]


def _make_sft_record(category: str, messages: list[dict]) -> Record:
    content = json.dumps(messages, ensure_ascii=False)
    return Record(
        id=Record.make_id(content),
        source="synthetic/adversarial-refusal",
        source_type="qa",
        content=content,
        language="rust",
        license="synthetic",
        metadata={
            "method": "adversarial-refusal",
            "category": category,
            "collected_at": today_str(),
            "anchor_style": "modern",
            "training_permitted": True,
        },
    )


def _make_dpo_record(source_tag: str, messages: list[dict]) -> Record:
    content = json.dumps(messages, ensure_ascii=False)
    return Record(
        id=Record.make_id(content),
        source=f"synthetic/adversarial-dpo-{source_tag}",
        source_type="qa",
        content=content,
        language="rust",
        license="synthetic",
        metadata={
            "method": f"adversarial-dpo-{source_tag}",
            "collected_at": today_str(),
            "anchor_style": "modern",
            "training_permitted": True,
        },
    )


def generate_category(
    category: str,
    scenarios: list[tuple[str, str]],
    phrasings: list[str],
    correct_fn,
    rejected_fn,
    target_count: int,
    seed: int,
) -> tuple[list[Record], list[Record], list[Record]]:
    """Generate SFT + DPO records for one category.

    Returns (sft_records, dpo_chosen, dpo_rejected).
    """
    rng = random.Random(seed)

    # Cross-product of scenarios x phrasings
    pairs = list(itertools.product(scenarios, phrasings))
    rng.shuffle(pairs)

    # Sample down to target count
    selected = pairs[:target_count]

    sft_records: list[Record] = []
    dpo_chosen: list[Record] = []
    dpo_rejected: list[Record] = []

    for (scenario, desc), phrasing_template in selected:
        user_msg = phrasing_template.format(scenario=scenario, desc=desc)

        correct_resp = correct_fn(scenario, desc, user_msg)
        rejected_resp = rejected_fn(scenario, desc, user_msg)

        # SFT record (correct refusal)
        correct_messages = _build_messages(user_msg, correct_resp)
        sft_records.append(_make_sft_record(category, correct_messages))

        # DPO chosen (correct)
        dpo_chosen.append(_make_dpo_record("chosen", correct_messages))

        # DPO rejected (deprecated)
        rejected_messages = _build_messages(user_msg, rejected_resp)
        dpo_rejected.append(_make_dpo_record("rejected", rejected_messages))

    return sft_records, dpo_chosen, dpo_rejected


@app.command()
def main(
    out_dir: Path = typer.Option(DATA_DIR, "--out-dir", help="Output directory"),
    seed: int = typer.Option(42, "--seed", help="Random seed for reproducibility"),
) -> None:
    """Generate adversarial refusal SFT and DPO training examples."""
    all_sft: list[Record] = []
    all_chosen: list[Record] = []
    all_rejected: list[Record] = []

    table = Table(title="Adversarial Refusal Generation")
    table.add_column("Category", style="cyan")
    table.add_column("SFT", justify="right", style="green")
    table.add_column("DPO Pairs", justify="right", style="yellow")

    for cat_name, cat_cfg in CATEGORIES.items():
        sft, chosen, rejected = generate_category(
            category=cat_name,
            scenarios=cat_cfg["scenarios"],
            phrasings=cat_cfg["phrasings"],
            correct_fn=cat_cfg["correct_fn"],
            rejected_fn=cat_cfg["rejected_fn"],
            target_count=cat_cfg["target_count"],
            seed=seed,
        )
        all_sft.extend(sft)
        all_chosen.extend(chosen)
        all_rejected.extend(rejected)
        table.add_row(cat_name, str(len(sft)), str(len(chosen)))

    console.print(table)

    # Write output files
    sft_path = out_dir / "adversarial-refusals.jsonl"
    chosen_path = out_dir / "dpo-chosen-adversarial.jsonl"
    rejected_path = out_dir / "dpo-rejected-adversarial.jsonl"

    sft_count = write_jsonl(all_sft, sft_path)
    chosen_count = write_jsonl(all_chosen, chosen_path)
    rejected_count = write_jsonl(all_rejected, rejected_path)

    console.print(f"\n[bold green]SFT records:[/]     {sft_count:>4}  ->  {sft_path}")
    console.print(f"[bold green]DPO chosen:[/]      {chosen_count:>4}  ->  {chosen_path}")
    console.print(f"[bold green]DPO rejected:[/]    {rejected_count:>4}  ->  {rejected_path}")
    console.print(f"[bold]Total examples:[/]  {sft_count + chosen_count + rejected_count}")


if __name__ == "__main__":
    app()
