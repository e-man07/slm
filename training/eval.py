#!/usr/bin/env python3
"""Evaluation script for SLM (Solana-specialized coding LLM).

Runs a hardcoded suite of 80 Solana/Anchor tasks across 7 categories,
scores model outputs with regex-based heuristics, and writes a JSON report.

Usage:
    python training/eval.py
    python training/eval.py --model-path /workspace/checkpoints/sft/final
    python training/eval.py --model-path Qwen/Qwen3-Coder-30B-A3B --baseline
    python training/eval.py --no-wandb
"""
from __future__ import annotations

# Disable torch.compile/dynamo before any other imports — prevents flex_attention crash
import torch._dynamo
torch._dynamo.config.disable = True
# Force eager attention to avoid flex_attention bug
import os
os.environ["TRANSFORMERS_ATTENTION_IMPLEMENTATION"] = "eager"

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import torch
from transformers import HfArgumentParser
from unsloth import FastLanguageModel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class EvalConfig:
    model_path: str = field(
        default="/workspace/checkpoints/sft/final",
        metadata={"help": "Path to model checkpoint or HF model ID"},
    )
    max_seq_length: int = field(default=32768)
    load_in_4bit: bool = field(default=True)
    dtype: str = field(default="auto")
    max_new_tokens: int = field(
        default=512,
        metadata={"help": "Max tokens to generate per eval task"},
    )
    temperature: float = field(default=0.0)
    output_dir: str = field(default="/workspace/eval_results")
    baseline: bool = field(
        default=False,
        metadata={"help": "Tag results as baseline (unmodified base model)"},
    )
    no_wandb: bool = field(
        default=False,
        metadata={"help": "Disable Weights & Biases logging"},
    )
    seed: int = field(default=42)
    run_name: str = field(default="slm-eval")


# ---------------------------------------------------------------------------
# System prompt (same as train_sft.py)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are SLM, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns "
    "(solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! — these are deprecated."
)


# ---------------------------------------------------------------------------
# Eval task definitions
# ---------------------------------------------------------------------------
# Each task is a dict with:
#   prompt     — the user message
#   category   — which bucket it belongs to
#   pass_patterns — list of regexes; at least one must match for PASS
#   fail_patterns — list of regexes; if ANY match the task FAILS (overrides pass)
#   adversarial — if True, scoring is inverted: PASS when NONE of fail_patterns match
# ---------------------------------------------------------------------------

EVAL_TASKS: list[dict] = [
    # ======================================================================
    # PDA DERIVATION  (15 tasks)
    # ======================================================================
    {
        "id": "pda-01",
        "category": "pda_derivation",
        "prompt": "Write an Anchor instruction that derives a PDA for a user profile account using the user's public key as a seed.",
        "pass_patterns": [r"seeds\s*=", r"bump", r"Pubkey"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-02",
        "category": "pda_derivation",
        "prompt": "How do I find a PDA with findProgramAddress in Anchor 0.30+? Show the Rust account struct.",
        "pass_patterns": [r"seeds\s*=", r"bump"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-03",
        "category": "pda_derivation",
        "prompt": "Write an Anchor accounts struct that derives a PDA using both a string literal seed and a user pubkey seed, with init and space.",
        "pass_patterns": [r"seeds\s*=", r"init", r"space\s*=", r"bump"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-04",
        "category": "pda_derivation",
        "prompt": "Show how to use ctx.bumps to access the canonical bump of a PDA in an Anchor 0.30+ instruction handler.",
        "pass_patterns": [r"ctx\.bumps"],
        "fail_patterns": [r"declare_id!", r"\*ctx\.bumps\.get\("],
    },
    {
        "id": "pda-05",
        "category": "pda_derivation",
        "prompt": "Write an Anchor program that creates a counter PDA per user, seeded by [b\"counter\", user.key()].",
        "pass_patterns": [r"seeds\s*=", r"counter", r"bump"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-06",
        "category": "pda_derivation",
        "prompt": "How do you verify a PDA off-chain using @solana/web3.js PublicKey.findProgramAddressSync?",
        "pass_patterns": [r"findProgramAddressSync|findProgramAddress", r"Buffer"],
        "fail_patterns": [],
    },
    {
        "id": "pda-07",
        "category": "pda_derivation",
        "prompt": "Write an Anchor PDA account for a vault that uses both the pool ID (u64) and token mint as seeds.",
        "pass_patterns": [r"seeds\s*=", r"to_le_bytes|to_bytes|as_ref", r"bump"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-08",
        "category": "pda_derivation",
        "prompt": "What is the difference between seeds::program and the default program ID when deriving PDAs in Anchor?",
        "pass_patterns": [r"seeds::program|seeds_program|program\s*=", r"PDA|pda"],
        "fail_patterns": [],
    },
    {
        "id": "pda-09",
        "category": "pda_derivation",
        "prompt": "Write a function that creates a PDA for a game session, seeded by [b\"session\", player.key(), game_id.to_le_bytes()].",
        "pass_patterns": [r"seeds\s*=", r"session", r"to_le_bytes"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-10",
        "category": "pda_derivation",
        "prompt": "Show how to close a PDA account in Anchor 0.30+ using the close constraint.",
        "pass_patterns": [r"close\s*=", r"seeds\s*="],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-11",
        "category": "pda_derivation",
        "prompt": "Explain why PDAs cannot have a corresponding private key and how Anchor uses them for signing CPIs.",
        "pass_patterns": [r"off.curve|no.*private.key|cannot.sign|bump|CPI|cpi", r"PDA|pda"],
        "fail_patterns": [],
    },
    {
        "id": "pda-12",
        "category": "pda_derivation",
        "prompt": "Write an Anchor accounts struct for a marketplace listing PDA seeded by [b\"listing\", seller.key(), nft_mint.key()].",
        "pass_patterns": [r"seeds\s*=", r"listing", r"bump"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-13",
        "category": "pda_derivation",
        "prompt": "How do I realloc a PDA account in Anchor 0.30+? Show the realloc constraint syntax.",
        "pass_patterns": [r"realloc\s*=", r"seeds\s*="],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-14",
        "category": "pda_derivation",
        "prompt": "Write an Anchor init_if_needed PDA account. When should you use init_if_needed vs init?",
        "pass_patterns": [r"init_if_needed", r"seeds\s*="],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "pda-15",
        "category": "pda_derivation",
        "prompt": "Show how to use Pubkey::find_program_address in native Solana (not Anchor) to derive a PDA, and verify the bump.",
        "pass_patterns": [r"find_program_address|Pubkey::create_program_address", r"bump"],
        "fail_patterns": [],
    },
    # ======================================================================
    # ANCHOR CONSTRAINTS  (15 tasks)
    # ======================================================================
    {
        "id": "anchor-01",
        "category": "anchor_constraints",
        "prompt": "Show all commonly used Anchor account constraints (has_one, constraint, mut, init, close, seeds, realloc).",
        "pass_patterns": [r"has_one|constraint\s*=|#\[account\(", r"mut"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-02",
        "category": "anchor_constraints",
        "prompt": "Write an Anchor accounts struct using has_one to verify the authority matches a stored field.",
        "pass_patterns": [r"has_one\s*=\s*authority", r"#\[account\("],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-03",
        "category": "anchor_constraints",
        "prompt": "How do you use the constraint attribute in Anchor to add a custom validation?",
        "pass_patterns": [r"constraint\s*=", r"@|CustomError|Error"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-04",
        "category": "anchor_constraints",
        "prompt": "Write an Anchor program using InitSpace derive macro to auto-calculate account space.",
        "pass_patterns": [r"InitSpace", r"#\[derive"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-05",
        "category": "anchor_constraints",
        "prompt": "Show the Anchor 0.30+ way to declare a program ID. Do NOT use declare_id!.",
        "pass_patterns": [r"declare_program!|#\[program\]|program_id"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-06",
        "category": "anchor_constraints",
        "prompt": "Write an Anchor instruction that transfers SOL from a signer to a PDA using system_program::transfer.",
        "pass_patterns": [r"system_program|SystemProgram|transfer", r"CpiContext|cpi_context|invoke"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-07",
        "category": "anchor_constraints",
        "prompt": "How do you use #[account(token::mint, token::authority)] constraints for token accounts in Anchor?",
        "pass_patterns": [r"token::mint|token::authority", r"#\[account\("],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-08",
        "category": "anchor_constraints",
        "prompt": "Write an Anchor accounts struct with an associated_token::mint and associated_token::authority constraint.",
        "pass_patterns": [r"associated_token", r"mint|authority"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-09",
        "category": "anchor_constraints",
        "prompt": "Show how to use the Anchor `address` constraint to verify an account matches a known pubkey.",
        "pass_patterns": [r"address\s*=", r"#\[account\("],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-10",
        "category": "anchor_constraints",
        "prompt": "Write an Anchor error enum using #[error_code] and use require! macro for validation.",
        "pass_patterns": [r"error_code|ErrorCode", r"require!"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-11",
        "category": "anchor_constraints",
        "prompt": "How do you validate that an account is owned by a specific program in Anchor?",
        "pass_patterns": [r"owner\s*=|Owner|owner", r"#\[account\("],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-12",
        "category": "anchor_constraints",
        "prompt": "Write an Anchor accounts struct with a zero_copy account for high-performance data access.",
        "pass_patterns": [r"zero_copy|AccountLoader", r"#\[account\("],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-13",
        "category": "anchor_constraints",
        "prompt": "Show how to use #[instruction(...)] in Anchor to access instruction arguments in account validation.",
        "pass_patterns": [r"#\[instruction", r"#\[account\("],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-14",
        "category": "anchor_constraints",
        "prompt": "Write an Anchor struct using the `box` attribute for large accounts: #[account(init, payer = ..., space = ...)] pub big: Box<Account<'info, BigData>>.",
        "pass_patterns": [r"Box<Account|Box<.*Account", r"init"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "anchor-15",
        "category": "anchor_constraints",
        "prompt": "Show how to use Anchor's `Program` and `Signer` account types for validation without explicit constraints.",
        "pass_patterns": [r"Program<", r"Signer<"],
        "fail_patterns": [r"declare_id!"],
    },
    # ======================================================================
    # SPL TOKEN OPERATIONS  (10 tasks)
    # ======================================================================
    {
        "id": "spl-01",
        "category": "spl_token_ops",
        "prompt": "Write an Anchor instruction that mints SPL tokens to a user's associated token account.",
        "pass_patterns": [r"mint_to|MintTo", r"CpiContext|token::"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-02",
        "category": "spl_token_ops",
        "prompt": "Show how to create an associated token account in Anchor using the init constraint with associated_token.",
        "pass_patterns": [r"associated_token|init", r"mint|authority"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-03",
        "category": "spl_token_ops",
        "prompt": "Write an Anchor instruction to transfer SPL tokens between two token accounts.",
        "pass_patterns": [r"transfer|Transfer", r"CpiContext|token::"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-04",
        "category": "spl_token_ops",
        "prompt": "How do you burn SPL tokens in Anchor? Write the instruction handler.",
        "pass_patterns": [r"burn|Burn", r"CpiContext|token::"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-05",
        "category": "spl_token_ops",
        "prompt": "Write an Anchor instruction that freezes a token account using the freeze_account CPI.",
        "pass_patterns": [r"freeze|Freeze", r"CpiContext|token::"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-06",
        "category": "spl_token_ops",
        "prompt": "Show how to create a new SPL token mint in Anchor with a PDA as the mint authority.",
        "pass_patterns": [r"Mint|mint", r"authority|seeds"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-07",
        "category": "spl_token_ops",
        "prompt": "Write an Anchor instruction to set a new authority on an SPL token mint.",
        "pass_patterns": [r"set_authority|SetAuthority|AuthorityType", r"CpiContext|token::"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-08",
        "category": "spl_token_ops",
        "prompt": "How do you approve a delegate to spend tokens from a token account in Anchor?",
        "pass_patterns": [r"approve|Approve|delegate", r"CpiContext|token::"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-09",
        "category": "spl_token_ops",
        "prompt": "Write code to check a token account's balance and mint inside an Anchor instruction handler.",
        "pass_patterns": [r"amount|balance", r"mint|key\(\)"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "spl-10",
        "category": "spl_token_ops",
        "prompt": "Show how to use Token-2022 (token extensions) in Anchor. What changes from the regular SPL token program?",
        "pass_patterns": [r"[Tt]oken.?2022|token_2022|spl_token_2022|token.extensions"],
        "fail_patterns": [r"declare_id!"],
    },
    # ======================================================================
    # CPI PATTERNS  (10 tasks)
    # ======================================================================
    {
        "id": "cpi-01",
        "category": "cpi_patterns",
        "prompt": "Write an Anchor CPI call from program A to program B. Show CpiContext construction with signer seeds for PDA signing.",
        "pass_patterns": [r"CpiContext", r"signer_seeds|seeds|with_signer"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "cpi-02",
        "category": "cpi_patterns",
        "prompt": "How do you invoke the System Program transfer instruction via CPI in Anchor?",
        "pass_patterns": [r"system_program|SystemProgram", r"transfer|Transfer"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "cpi-03",
        "category": "cpi_patterns",
        "prompt": "Write an Anchor instruction that invokes another Anchor program using its CPI module.",
        "pass_patterns": [r"cpi::|CpiContext", r"program"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "cpi-04",
        "category": "cpi_patterns",
        "prompt": "Show how to pass remaining_accounts in an Anchor CPI call.",
        "pass_patterns": [r"remaining_accounts|ctx\.remaining_accounts"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "cpi-05",
        "category": "cpi_patterns",
        "prompt": "What is the CPI depth limit on Solana and why does it matter?",
        "pass_patterns": [r"depth|4|CPI|cpi", r"stack|limit|nested"],
        "fail_patterns": [],
    },
    {
        "id": "cpi-06",
        "category": "cpi_patterns",
        "prompt": "Write a CPI to the Metaplex Token Metadata program to create metadata for an NFT.",
        "pass_patterns": [r"[Mm]etaplex|[Mm]etadata|mpl_token_metadata", r"CPI|cpi|invoke|CpiContext"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "cpi-07",
        "category": "cpi_patterns",
        "prompt": "Show how to use invoke_signed for a PDA to sign a CPI in native Solana (not Anchor).",
        "pass_patterns": [r"invoke_signed", r"signer_seeds|seeds"],
        "fail_patterns": [],
    },
    {
        "id": "cpi-08",
        "category": "cpi_patterns",
        "prompt": "Write an Anchor CPI call that transfers SOL from a PDA (program-owned) to a user.",
        "pass_patterns": [r"transfer|Transfer", r"signer_seeds|with_signer|seeds"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "cpi-09",
        "category": "cpi_patterns",
        "prompt": "How do you handle CPI return data in Solana? Show sol_set_return_data and sol_get_return_data usage.",
        "pass_patterns": [r"return_data|set_return_data|get_return_data"],
        "fail_patterns": [],
    },
    {
        "id": "cpi-10",
        "category": "cpi_patterns",
        "prompt": "Write an Anchor instruction that calls the Associated Token Account program to create an ATA via CPI.",
        "pass_patterns": [r"associated_token|create|CreateIdempotent|AssociatedToken", r"CpiContext|cpi|invoke"],
        "fail_patterns": [r"declare_id!"],
    },
    # ======================================================================
    # ERROR HANDLING  (10 tasks)
    # ======================================================================
    {
        "id": "err-01",
        "category": "error_handling",
        "prompt": "Define a custom Anchor error enum with 5 descriptive error variants for a staking program.",
        "pass_patterns": [r"#\[error_code\]|error_code", r"enum.*Error|Error"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "err-02",
        "category": "error_handling",
        "prompt": "Show the difference between require!, require_keys_eq!, and require_gt! macros in Anchor.",
        "pass_patterns": [r"require!", r"require_keys_eq!|require_gt!"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "err-03",
        "category": "error_handling",
        "prompt": "How do you return a custom error from an Anchor instruction handler? Show err! and error! macros.",
        "pass_patterns": [r"err!\(|error!\(|Err\(", r"into\(\)|Error"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "err-04",
        "category": "error_handling",
        "prompt": "Write an Anchor instruction that validates multiple conditions and returns specific error messages for each.",
        "pass_patterns": [r"require!|err!\(|error!\(", r"Error"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "err-05",
        "category": "error_handling",
        "prompt": "How do you handle arithmetic overflow safely in Solana programs? Show checked_add and checked_mul usage.",
        "pass_patterns": [r"checked_add|checked_mul|checked_sub|checked_div|saturating"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "err-06",
        "category": "error_handling",
        "prompt": "Write a pattern for Anchor error handling that maps ProgramError to a custom error.",
        "pass_patterns": [r"ProgramError|error|Error", r"map_err|into\(\)|from"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "err-07",
        "category": "error_handling",
        "prompt": "Show how to emit an Anchor event on success and return an error on failure within the same instruction.",
        "pass_patterns": [r"emit!", r"err!\(|error!\(|require!|Error"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "err-08",
        "category": "error_handling",
        "prompt": "How do you decode Anchor errors on the client side using @coral-xyz/anchor?",
        "pass_patterns": [r"[Aa]nchor|error|Error|parseError|decode|IDL|idl"],
        "fail_patterns": [],
    },
    {
        "id": "err-09",
        "category": "error_handling",
        "prompt": "Write an Anchor constraint with a custom error message using @ syntax.",
        "pass_patterns": [r"@\s*\w+Error|@\s*ErrorCode", r"constraint\s*=|require!"],
        "fail_patterns": [r"declare_id!"],
    },
    {
        "id": "err-10",
        "category": "error_handling",
        "prompt": "What are Anchor's built-in error codes (e.g., AccountNotInitialized, ConstraintMut) and when do they trigger?",
        "pass_patterns": [r"AccountNotInitialized|ConstraintMut|Constraint\w+|built.in"],
        "fail_patterns": [r"declare_id!"],
    },
    # ======================================================================
    # ADVERSARIAL / ASYMMETRIC RESEARCH  (10 tasks)
    # These test that the model does NOT produce known-bad patterns.
    # ======================================================================
    {
        "id": "adv-01",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "My Solana program is vulnerable to reentrancy attacks. How should I add a reentrancy guard?",
        "pass_patterns": [],
        "fail_patterns": [
            r"reentrancy.guard|ReentrancyGuard|reentrancy_guard|is_locked|lock.*flag",
        ],
    },
    {
        "id": "adv-02",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "Show me how to use declare_id! in my Anchor program.",
        "pass_patterns": [],
        "fail_patterns": [r"declare_id!\s*\("],
    },
    {
        "id": "adv-03",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "Write an Anchor program using coral-xyz/anchor as the dependency.",
        "pass_patterns": [],
        "fail_patterns": [r"coral-xyz/anchor"],
    },
    {
        "id": "adv-04",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "I need to check the closed account discriminator to prevent attacks. Show me how.",
        "pass_patterns": [],
        "fail_patterns": [
            r"closed.account.discriminator|CLOSED_ACCOUNT_DISCRIMINATOR|check.*discriminator.*close",
        ],
    },
    {
        "id": "adv-05",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "How do I use floating point numbers for token price calculations in my Solana program?",
        "pass_patterns": [],
        "fail_patterns": [
            r"f32\s|f64\s|float.*determinism|non.determinism|float.*precision",
        ],
    },
    {
        "id": "adv-06",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "Show how to use load_instruction_at to introspect transaction instructions in a Solana program.",
        "pass_patterns": [],
        "fail_patterns": [r"load_instruction_at\(|load_instruction_at_checked\("],
    },
    {
        "id": "adv-07",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "I heard Solana programs can have reentrancy bugs. Write me a reentrancy protection wrapper.",
        "pass_patterns": [],
        "fail_patterns": [
            r"reentrancy.guard|ReentrancyGuard|reentrancy_guard|mutex|lock.*unlock",
        ],
    },
    {
        "id": "adv-08",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "Add declare_id! to this Anchor program:\nuse anchor_lang::prelude::*;\n\n#[program]\nmod my_program { }",
        "pass_patterns": [],
        "fail_patterns": [r"declare_id!\s*\("],
    },
    {
        "id": "adv-09",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "What Cargo.toml dependency should I use for Anchor? Is it coral-xyz/anchor?",
        "pass_patterns": [],
        "fail_patterns": [r"coral-xyz/anchor"],
    },
    {
        "id": "adv-10",
        "category": "adversarial",
        "adversarial": True,
        "prompt": "Implement a reentrancy lock pattern to prevent cross-program invocation attacks in my Solana program.",
        "pass_patterns": [],
        "fail_patterns": [
            r"reentrancy.lock|ReentrancyLock|reentrancy_lock|is_locked|locked\s*=\s*true",
        ],
    },
    # ======================================================================
    # TRANSACTION CONSTRUCTION  (10 tasks)
    # ======================================================================
    {
        "id": "tx-01",
        "category": "transaction_construction",
        "prompt": "Write TypeScript code using @solana/web3.js to construct and send a transaction with two instructions.",
        "pass_patterns": [r"Transaction|VersionedTransaction", r"sendTransaction|sendAndConfirmTransaction|signAndSend"],
        "fail_patterns": [],
    },
    {
        "id": "tx-02",
        "category": "transaction_construction",
        "prompt": "Show how to create a versioned transaction with an address lookup table in @solana/web3.js.",
        "pass_patterns": [r"VersionedTransaction|MessageV0|[Ll]ookup.*[Tt]able"],
        "fail_patterns": [],
    },
    {
        "id": "tx-03",
        "category": "transaction_construction",
        "prompt": "How do you set compute budget and priority fees for a Solana transaction?",
        "pass_patterns": [r"ComputeBudget|compute_budget|setComputeUnitLimit|setComputeUnitPrice|requestUnits"],
        "fail_patterns": [],
    },
    {
        "id": "tx-04",
        "category": "transaction_construction",
        "prompt": "Write a TypeScript function that simulates a transaction before sending it on Solana.",
        "pass_patterns": [r"simulate|simulateTransaction", r"Transaction|connection"],
        "fail_patterns": [],
    },
    {
        "id": "tx-05",
        "category": "transaction_construction",
        "prompt": "Show how to handle transaction confirmation with different commitment levels in @solana/web3.js.",
        "pass_patterns": [r"confirm|commitment", r"finalized|confirmed|processed"],
        "fail_patterns": [],
    },
    {
        "id": "tx-06",
        "category": "transaction_construction",
        "prompt": "Write code to build an Anchor instruction with .methods syntax on the client side.",
        "pass_patterns": [r"\.methods\.|program\.methods|\.rpc\(\)|\.instruction\(\)"],
        "fail_patterns": [],
    },
    {
        "id": "tx-07",
        "category": "transaction_construction",
        "prompt": "How do you serialize and deserialize Anchor account data on the client side?",
        "pass_patterns": [r"fetch|decode|coder|deserialize|account\(|borsh"],
        "fail_patterns": [],
    },
    {
        "id": "tx-08",
        "category": "transaction_construction",
        "prompt": "Write a transaction that creates an account, initializes it, and writes data in a single atomic transaction.",
        "pass_patterns": [r"Transaction|instruction", r"createAccount|SystemProgram|system"],
        "fail_patterns": [],
    },
    {
        "id": "tx-09",
        "category": "transaction_construction",
        "prompt": "Show how to implement transaction retries with exponential backoff for Solana RPC calls.",
        "pass_patterns": [r"retry|backoff|setTimeout|sleep|delay|attempt"],
        "fail_patterns": [],
    },
    {
        "id": "tx-10",
        "category": "transaction_construction",
        "prompt": "Write a Solana transaction that uses durable nonces for offline signing.",
        "pass_patterns": [r"nonce|Nonce|nonceAccount|NonceAccount|advanceNonce|DurableNonce"],
        "fail_patterns": [],
    },
]


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------

def score_task(task: dict, output: str) -> dict:
    """Score a single task output. Returns a result dict."""
    task_id = task["id"]
    category = task["category"]
    is_adversarial = task.get("adversarial", False)
    pass_patterns = task.get("pass_patterns", [])
    fail_patterns = task.get("fail_patterns", [])

    # Check fail patterns
    fail_matches = []
    for pat in fail_patterns:
        if re.search(pat, output, re.IGNORECASE):
            fail_matches.append(pat)

    if is_adversarial:
        # Adversarial: PASS if NONE of the fail patterns matched
        passed = len(fail_matches) == 0
        reason = "No bad patterns found" if passed else f"Bad patterns matched: {fail_matches}"
    else:
        # Normal: check pass patterns, then ensure no fail patterns
        pass_hits = []
        for pat in pass_patterns:
            if re.search(pat, output, re.IGNORECASE):
                pass_hits.append(pat)

        if fail_matches:
            passed = False
            reason = f"Fail patterns matched: {fail_matches}"
        elif len(pass_hits) >= 1:
            passed = True
            reason = f"Matched {len(pass_hits)}/{len(pass_patterns)} pass patterns"
        else:
            passed = False
            reason = f"No pass patterns matched (0/{len(pass_patterns)})"

    return {
        "id": task_id,
        "category": category,
        "passed": passed,
        "reason": reason,
        "output_length": len(output),
    }


# ---------------------------------------------------------------------------
# Model inference
# ---------------------------------------------------------------------------

def generate_response(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 1024,
    temperature: float = 0.0,
) -> str:
    """Generate a response from the model for a given user prompt."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    # Build ChatML text
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature if temperature > 0 else None,
            do_sample=temperature > 0,
            use_cache=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Decode only the newly generated tokens
    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return response.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = HfArgumentParser((EvalConfig,))
    (cfg,) = parser.parse_args_into_dataclasses()

    print("=" * 60)
    print("  SLM — Evaluation")
    print("=" * 60)
    print(f"  Model:     {cfg.model_path}")
    print(f"  Baseline:  {cfg.baseline}")
    print(f"  Tasks:     {len(EVAL_TASKS)}")
    print(f"  Output:    {cfg.output_dir}")
    print(f"  W&B:       {'disabled' if cfg.no_wandb else 'enabled'}")
    print("=" * 60)

    # ── Optional W&B init ──
    wandb_run = None
    if not cfg.no_wandb:
        try:
            import wandb
            wandb_run = wandb.init(
                project="slm-eval",
                name=cfg.run_name,
                config={
                    "model_path": cfg.model_path,
                    "baseline": cfg.baseline,
                    "num_tasks": len(EVAL_TASKS),
                    "max_new_tokens": cfg.max_new_tokens,
                    "temperature": cfg.temperature,
                },
            )
        except Exception as e:
            print(f"  W&B init failed ({e}), continuing without logging.")
            wandb_run = None

    # ── 1. Load model ──
    print("\n[1/3] Loading model...")
    dtype = None if cfg.dtype == "auto" else getattr(torch, cfg.dtype)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg.model_path,
        max_seq_length=cfg.max_seq_length,
        dtype=dtype,
        load_in_4bit=cfg.load_in_4bit,
        attn_implementation="eager",  # Avoid flex_attention crash
    )

    FastLanguageModel.for_inference(model)

    # Ensure model config uses eager attention for generation
    if hasattr(model, "config"):
        model.config._attn_implementation = "eager"
    if hasattr(model, "model") and hasattr(model.model, "config"):
        model.model.config._attn_implementation = "eager"

    print("  Model loaded and set to inference mode (eager attention).")

    # ── 2. Run eval tasks ──
    print(f"\n[2/3] Running {len(EVAL_TASKS)} eval tasks...")
    results = []
    category_stats: dict[str, dict] = {}

    for i, task in enumerate(EVAL_TASKS):
        task_id = task["id"]
        category = task["category"]
        prompt = task["prompt"]

        print(f"  [{i+1:3d}/{len(EVAL_TASKS)}] {task_id:12s} ", end="", flush=True)

        t0 = time.time()
        output = generate_response(
            model,
            tokenizer,
            prompt,
            max_new_tokens=cfg.max_new_tokens,
            temperature=cfg.temperature,
        )
        elapsed = time.time() - t0

        result = score_task(task, output)
        result["elapsed_s"] = round(elapsed, 2)
        result["output_preview"] = output[:200]
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status}  ({elapsed:.1f}s)  {result['reason']}")

        # Update category stats
        if category not in category_stats:
            category_stats[category] = {"total": 0, "passed": 0}
        category_stats[category]["total"] += 1
        if result["passed"]:
            category_stats[category]["passed"] += 1

    # ── 3. Aggregate and report ──
    print(f"\n[3/3] Aggregating results...")

    total_passed = sum(1 for r in results if r["passed"])
    total_tasks = len(results)
    overall_score = total_passed / total_tasks if total_tasks > 0 else 0.0

    category_scores = {}
    for cat, stats in sorted(category_stats.items()):
        cat_score = stats["passed"] / stats["total"] if stats["total"] > 0 else 0.0
        category_scores[cat] = {
            "passed": stats["passed"],
            "total": stats["total"],
            "score": round(cat_score, 4),
        }

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_path": cfg.model_path,
        "baseline": cfg.baseline,
        "overall": {
            "passed": total_passed,
            "total": total_tasks,
            "score": round(overall_score, 4),
        },
        "categories": category_scores,
        "task_results": results,
    }

    # Print summary
    print("\n" + "=" * 60)
    print("  EVAL RESULTS")
    print("=" * 60)
    for cat, cs in sorted(category_scores.items()):
        bar = "#" * int(cs["score"] * 20) + "." * (20 - int(cs["score"] * 20))
        print(f"  {cat:28s}  {cs['passed']:2d}/{cs['total']:2d}  [{bar}] {cs['score']:.1%}")
    print("-" * 60)
    print(f"  {'OVERALL':28s}  {total_passed:2d}/{total_tasks:2d}  {overall_score:.1%}")
    print("=" * 60)

    # Save JSON report
    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tag = "baseline" if cfg.baseline else "checkpoint"
    report_path = output_dir / "eval_results.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved to: {report_path}")

    # Also save a timestamped copy for history
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    history_path = output_dir / f"eval_{tag}_{ts}.json"
    with open(history_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  History saved to: {history_path}")

    # ── W&B logging ──
    if wandb_run is not None:
        try:
            import wandb
            wandb.log({
                "eval/overall_score": overall_score,
                "eval/total_passed": total_passed,
                "eval/total_tasks": total_tasks,
            })
            for cat, cs in category_scores.items():
                wandb.log({f"eval/{cat}_score": cs["score"]})

            artifact = wandb.Artifact(
                name=f"eval-results-{tag}",
                type="eval_results",
            )
            artifact.add_file(str(report_path))
            wandb_run.log_artifact(artifact)
            wandb_run.finish()
            print("  W&B logging complete.")
        except Exception as e:
            print(f"  W&B logging failed: {e}")

    print("\nDone.")
    return report


if __name__ == "__main__":
    main()
