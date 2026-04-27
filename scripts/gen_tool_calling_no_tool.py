"""Group C: No-tool-needed examples (target: 1,500).

Critical for preventing the model from over-calling tools. Each record is a
simple system+user+assistant trio with NO <tool_call> tags in the assistant
turn — teaches the model that conceptual questions, greetings, follow-ups,
and explicit "don't run anything" requests should be answered directly.

Subcategories:
  C1 Greetings ("hi", "hello", "thanks")            (100)
  C2 Solana conceptual Q&A                          (400)
  C3 Anchor conceptual Q&A                          (300)
  C4 Pinocchio conceptual Q&A                       (100)
  C5 Follow-ups referring to prior tool result      (250)
  C6 "Don't run anything, just explain"             (150)
  C7 Hypothetical / planning                        (100)
  C8 Reasoning over user-provided info              (100)

Total = 1,500.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Iterator

from _tool_calling_common import GREETINGS, make_record, system_prompt, write_records_to_jsonl
from schema import Record

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "sft_tool_calling_no_tool.jsonl"

PLAN_TARGET = 1_500

TARGETS = {
    "C1_greetings": 100,
    "C2_solana_concept": 400,
    "C3_anchor_concept": 300,
    "C4_pinocchio_concept": 100,
    "C5_followup": 250,
    "C6_no_tool_explicit": 150,
    "C7_hypothetical": 100,
    "C8_user_provided_info": 100,
}


def _no_tool_record(category: str, subcategory: str, user_msg: str, response: str) -> Record:
    """Helper: build a 3-turn record with no tools."""
    messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": response},
    ]
    return make_record(messages, category, subcategory=subcategory)


# ── C1: Greetings ──


def gen_C1_greetings() -> Iterator[Record]:
    responses = [
        "Hello! What Solana or Anchor work can I help with?",
        "Hi! What do you want to build today?",
        "Hey! Ready to help with Solana development.",
        "You're welcome! Let me know if you need anything else.",
        "Anytime. What's next?",
        "Glad I could help.",
        "Good morning! How can I assist with your Solana program?",
        "Hi there. What are you working on?",
        "Doing well — what about you? What can I help with?",
        "Got it. Let me know what you'd like to do next.",
    ]
    rng = random.Random(201)
    for greeting in GREETINGS:
        for response in responses:
            yield _no_tool_record("C1_greetings", "greeting", greeting, response)


# ── C2: Solana conceptual Q&A ──


SOLANA_CONCEPTS = [
    ("What is a PDA in Solana?",
     "A Program Derived Address (PDA) is a public key that's deterministically derived from a program ID "
     "and a set of seeds. Unlike regular keypairs, a PDA has no corresponding private key — it's mathematically "
     "off the ed25519 curve. Programs can sign for PDAs they own using `invoke_signed`. Typical use: data "
     "accounts owned by a program, vault authorities, escrow state."),
    ("Explain how rent works on Solana.",
     "Solana accounts pay rent to remain on-chain. Currently, all accounts must be **rent-exempt**, meaning "
     "they hold at least 2 years' worth of rent in lamports based on their data size. The lamports stay in the "
     "account; there's no ongoing deduction. When you close an account, you can transfer those lamports back."),
    ("What's a CPI?",
     "Cross-Program Invocation (CPI) — one Solana program calling another. The runtime enforces a depth "
     "limit of 4. CPIs propagate signer privileges only for accounts the calling program signs for "
     "(via PDAs and `invoke_signed`). Typical pattern: your program CPIs into the SPL Token program to "
     "transfer tokens."),
    ("How do lamports relate to SOL?",
     "1 SOL = 1,000,000,000 (1 billion) lamports. Lamports are the atomic unit; SOL is just for human display. "
     "All on-chain math is in lamports."),
    ("What is the rent-exempt minimum for a 100-byte account?",
     "Use `Rent::get()?.minimum_balance(100)` in a program. As of the current rent params, ~890,880 lamports "
     "for a 100-byte account, but it varies — always compute it dynamically rather than hardcoding."),
    ("What's the difference between an account's owner and authority?",
     "**Owner** is the program ID that can mutate the account's data and lamports — set in the account header. "
     "**Authority** is application-level: a Pubkey field stored *inside* the account data that your program "
     "checks before allowing certain operations (e.g., a vault's authority can withdraw)."),
    ("Explain compute units and CU budget.",
     "Each transaction has a Compute Unit (CU) budget — by default 200K CU per instruction, max 1.4M CU per "
     "transaction. Every BPF instruction costs CU. You can request more with `ComputeBudgetInstruction::set_compute_unit_limit`. "
     "Pay attention: deeply nested CPIs and large account validations burn CU fast."),
    ("What is a signer in a Solana transaction?",
     "A signer is an account whose private key signed the transaction. Programs receive `is_signer = true` for "
     "those accounts. Signers prove authority for actions they're claiming (e.g., spending lamports from their account)."),
    ("How does Solana achieve sub-second finality?",
     "Through Tower BFT (variant of PBFT) on top of Proof of History. PoH provides a verifiable global clock; "
     "validators vote on block hashes; once 2/3+ stake votes for a block, it's optimistically confirmed. Full "
     "finality (rooted slot) takes ~12 seconds; optimistic confirmation is sub-second."),
    ("What is a transaction in Solana?",
     "A transaction is a signed bundle of one or more instructions. Each instruction targets a single program "
     "and includes a list of accounts plus instruction data. Transactions are atomic — all instructions succeed "
     "or all fail together."),
    ("Explain the difference between Solana and Ethereum from a smart-contract perspective.",
     "Solana programs are stateless — they execute against accounts passed in by the transaction. Ethereum "
     "contracts have storage built into the contract address. Solana is parallel-friendly because transactions "
     "declare their account dependencies upfront (Sealevel scheduler). Solana uses BPF/SBF; Ethereum uses EVM."),
    ("What is a slot?",
     "A slot is a fixed time window (~400ms) in which a chosen leader is allowed to produce a block. Not every "
     "slot has a block — leaders can skip. Slots are the basic unit of progress in Solana's clock."),
    ("What is an epoch?",
     "An epoch is 432,000 slots (~2 days). Stake activations and validator set changes take effect at epoch "
     "boundaries. Many staking-related operations are gated by epoch."),
    ("How do I sign for a PDA?",
     "Use `invoke_signed` with the PDA's seeds and bump as `signers_seeds`. Example: "
     "`invoke_signed(&ix, &accounts, &[&[b\"vault\", maker_pubkey.as_ref(), &[bump]]])`. "
     "The runtime re-derives the PDA from the seeds and verifies the program is the owner."),
    ("What's an associated token account (ATA)?",
     "An ATA is a deterministic SPL token account address derived from `(wallet, mint)`. Always use the "
     "Associated Token Account program (`spl-associated-token-account`) to create them — never derive your own. "
     "Most wallets and dApps assume tokens live in their ATA."),
    ("What's the difference between SPL Token and Token-2022?",
     "Token-2022 (also called Token Extensions) is a successor to the original SPL Token program with extension "
     "support: transfer hooks, transfer fees, confidential transfers, metadata pointer, interest-bearing tokens, "
     "etc. They're separate programs with separate token accounts — not backwards-compatible at the account level."),
    ("What are durable nonces?",
     "A durable nonce is a special on-chain account holding a recent blockhash that doesn't expire (unlike normal "
     "blockhashes that expire after 150 slots). Useful for offline signing — sign a transaction now, submit it days "
     "later. The nonce is consumed and updated on every use."),
    ("Explain Address Lookup Tables (ALTs).",
     "ALTs let you store an array of pubkeys on-chain and reference them by index in transactions. This compresses "
     "transaction size — instead of 32 bytes per account reference, you use a 1-byte index. Critical for "
     "transactions with 30+ accounts. Use `MessageV0` (versioned transactions) to leverage them."),
    ("What is `Clock::get()` for?",
     "`Clock::get()?` returns the current `Clock` sysvar: slot, epoch, unix_timestamp, leader_schedule_epoch. "
     "Used for timestamp gating (e.g., \"unlock at time T\"), epoch checks, slot-based logic. Note: "
     "`unix_timestamp` is the cluster's notion of real time — drifts a few seconds from wall clock."),
    ("Why is account ordering significant in a Solana instruction?",
     "Each instruction declares an `accounts` array in a specific order. Programs read them by position — `accounts[0]` "
     "is the first account, etc. The Sealevel runtime uses this order to determine which accounts can be parallelized "
     "across transactions. Mismatched ordering between client and program is a common source of `AccountOwnedByWrongProgram` "
     "or generic deserialization errors."),
]


def gen_C2_solana_concept() -> Iterator[Record]:
    rng = random.Random(202)
    paraphrases = [
        "{}",
        "Quick question: {}",
        "Hey, {}",
        "{} (no need to look at code)",
        "Just curious — {}",
    ]
    for q, a in SOLANA_CONCEPTS:
        for tmpl in paraphrases:
            yield _no_tool_record("C2_solana_concept", "concept", tmpl.format(q), a)


# ── C3: Anchor conceptual ──


ANCHOR_CONCEPTS = [
    ("What does `#[account]` do in Anchor?",
     "`#[account]` is a procedural macro that adds an 8-byte discriminator to a struct, marking it as a custom "
     "Anchor account. The discriminator is the SHA-256 hash of `\"account:{StructName}\"` truncated to 8 bytes. "
     "It's used at runtime to verify account types match before deserialization."),
    ("What does `#[derive(Accounts)]` do?",
     "It generates the validation logic for an account context struct. Each field with an attribute (`#[account(...)]`) "
     "produces runtime checks: signer, mut, init, has_one, seeds, bump, etc. The macro turns declarative constraints "
     "into procedural Rust code that runs before your instruction handler."),
    ("How does `#[derive(InitSpace)]` work?",
     "It generates a `INIT_SPACE` constant on the struct equal to the sum of `MAX_SIZE` for every field. Use it in "
     "`space = 8 + Counter::INIT_SPACE` instead of manually computing field sizes. The 8 is for the account discriminator."),
    ("Explain `init`, `init_if_needed`, and `mut` in account constraints.",
     "**`init`** creates a new account, charging the payer for rent and setting the program as owner. Errors if the "
     "account already exists.\n"
     "**`init_if_needed`** is like `init` but only creates if the account doesn't already exist (silent no-op otherwise). "
     "Avoid unless necessary — risks reinitialization attacks if not handled carefully.\n"
     "**`mut`** marks an account as mutable. Without `mut`, Anchor enforces read-only access."),
    ("What does `has_one` do in Anchor?",
     "`#[account(has_one = authority)]` enforces that the account's `authority` field equals the `authority` "
     "account passed in the context. Used for ownership checks: only the recorded authority can mutate this account."),
    ("How are PDAs created in Anchor?",
     "Use `#[account(seeds = [...], bump)]`. Anchor automatically derives the PDA from the seeds at runtime and "
     "verifies it matches the account passed in. The `bump` is auto-discovered (or you can pass it explicitly with "
     "`bump = stored_bump` for canonical bump enforcement)."),
    ("What is `ctx.bumps`?",
     "After Anchor validates a PDA constraint, the resolved bump is stored in `ctx.bumps`. Access via field name: "
     "`ctx.bumps.my_account`. **Don't use** the deprecated `ctx.bumps.get(\"name\")` form — that was the pre-0.30 syntax."),
    ("Explain `#[error_code]`.",
     "It generates a custom error enum that integrates with Anchor's error reporting. Each variant gets a numeric code "
     "(starting at 6000) and an optional `#[msg(\"...\")]` message displayed in client logs. Use `require!(cond, MyError::Variant)` "
     "to throw."),
    ("What's the difference between `Account<'info, T>` and `AccountInfo<'info>`?",
     "**`Account<T>`** does typed deserialization — Anchor reads the discriminator, deserializes the data into `T`, "
     "and gives you typed field access. Validates ownership.\n"
     "**`AccountInfo`** is raw — you get the lamports, data bytes, and owner with no deserialization. Use it when you "
     "need to handle accounts of unknown type or do CPI manually."),
]


def gen_C3_anchor_concept() -> Iterator[Record]:
    paraphrases = ["{}", "Anchor question: {}", "Can you explain — {}", "Help me understand: {}"]
    for q, a in ANCHOR_CONCEPTS:
        for tmpl in paraphrases:
            yield _no_tool_record("C3_anchor_concept", "anchor_concept", tmpl.format(q), a)


# ── C4: Pinocchio ──


PINOCCHIO_CONCEPTS = [
    ("What is Pinocchio?",
     "Pinocchio is a zero-copy, no-`std`, dependency-free framework for writing Solana programs. It's much smaller "
     "than Anchor (no codegen, no proc macros for accounts) and produces tighter BPF bytecode. Trade-off: you give up "
     "Anchor's account validation guarantees and have to handle deserialization manually."),
    ("When should I use Pinocchio over Anchor?",
     "Use Pinocchio when CU budget is tight and program size matters — Token-2022 transfer hooks, oracles called from "
     "many CPIs, or anything in the hot path of high-throughput dApps. Stick with Anchor for application logic where "
     "developer ergonomics and audit-friendliness outweigh CU savings."),
    ("Does Pinocchio work with Anchor IDLs?",
     "Not directly — Pinocchio doesn't generate an IDL. If you need client-side TypeScript types, you write them "
     "manually or use a tool like Codama. For programs with simple instruction shapes, this is manageable."),
]


def gen_C4_pinocchio_concept() -> Iterator[Record]:
    paraphrases = ["{}", "Tell me — {}", "Question on Pinocchio: {}", "Explain please: {}"]
    for q, a in PINOCCHIO_CONCEPTS:
        for tmpl in paraphrases:
            yield _no_tool_record("C4_pinocchio_concept", "pinocchio_concept", tmpl.format(q), a)


# ── C5: Follow-ups (synthetic — assume prior tool result in history) ──


def gen_C5_followup() -> Iterator[Record]:
    """Multi-turn: prior tool result, then a follow-up that needs reasoning, not another tool call."""
    scenarios = [
        # (prior_user, prior_assistant_with_tool, prior_result, follow_up_user, follow_up_assistant_no_tool)
        (
            "Read programs/counter/src/lib.rs.",
            'I\'ll read the file.\n<tool_call>{"name": "read_file", "arguments": {"path": "programs/counter/src/lib.rs"}}</tool_call>',
            '<tool_result name="read_file" status="success">\nFile: programs/counter/src/lib.rs (60 lines, showing 1-60)\n   1 | use anchor_lang::prelude::*;\n   2 |\n[...]\n</tool_result>',
            "Why is the bump stored on the counter account?",
            "Storing the bump on the account is the canonical bump enforcement pattern. When you re-derive the PDA "
            "later (in `increment`), you use the stored bump via `bump = counter.bump` — this guarantees the same "
            "PDA every time and prevents an attacker from passing a different valid (non-canonical) bump.",
        ),
        (
            "Find all Cargo.toml files.",
            'I\'ll search.\n<tool_call>{"name": "glob_files", "arguments": {"pattern": "**/Cargo.toml"}}</tool_call>',
            '<tool_result name="glob_files" status="success">\n3 files found:\nCargo.toml\nprograms/escrow/Cargo.toml\nprograms/oracle/Cargo.toml\n</tool_result>',
            "What's the difference between the workspace Cargo.toml and the program Cargo.toml files?",
            "The workspace `Cargo.toml` (at the root) declares `[workspace]` and lists the member programs. It doesn't "
            "have its own `[package]` section. Each program's `Cargo.toml` (e.g., `programs/escrow/Cargo.toml`) has its "
            "own `[package]` and `[dependencies]` and is what actually gets built into a `.so` file by `anchor build`.",
        ),
        (
            "What's in tests/counter.ts?",
            'Reading.\n<tool_call>{"name": "read_file", "arguments": {"path": "tests/counter.ts"}}</tool_call>',
            '<tool_result name="read_file" status="success">\nFile: tests/counter.ts (...lines)\n[...test body]\n</tool_result>',
            "Why does the test use `findProgramAddressSync` instead of just hardcoding the PDA?",
            "Because PDAs depend on the program ID, which differs between localnet/devnet/mainnet. `findProgramAddressSync` "
            "computes the PDA deterministically from the runtime program ID and the seeds, so the same test code works "
            "across clusters. Hardcoding would only work for one specific deployment.",
        ),
    ]

    for prior_user, prior_assistant, prior_result, follow_user, follow_assistant in scenarios:
        messages = [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prior_user},
            {"role": "assistant", "content": prior_assistant},
            {"role": "user", "content": prior_result},
            # First follow-up assistant turn isn't always needed — but include a brief one
            {"role": "assistant", "content": "(Read complete; output above.)"},
            # Now the actual follow-up
            {"role": "user", "content": follow_user},
            {"role": "assistant", "content": follow_assistant},
        ]
        yield make_record(messages, "C5_followup", subcategory="contextual_reasoning")


# ── C6: Explicit "don't run anything, just explain" ──


def gen_C6_no_tool_explicit() -> Iterator[Record]:
    pairs = [
        ("Without running any tools, explain how I'd add a `withdraw` instruction to a vault.",
         "A `withdraw` instruction needs:\n\n1. A `Withdraw` accounts context with the vault PDA (mut), the user's token "
         "account (mut), the user (signer + checks against vault.authority), and the SPL Token program.\n"
         "2. The handler does a CPI to `anchor_spl::token::transfer` from vault → user, signed by the vault PDA via "
         "`invoke_signed` with the vault's seeds.\n"
         "3. Deduct the withdrawn amount from `vault.balance` (use `checked_sub`).\n"
         "4. Add a `require!` to enforce a minimum balance or unlock time if needed."),
        ("Don't actually scaffold anything — just describe what files I'd need for a basic Anchor token vault.",
         "You'd need:\n\n"
         "- **`Anchor.toml`** — workspace + program ID + cluster config.\n"
         "- **`Cargo.toml`** (workspace) — declares the program crate as a member.\n"
         "- **`programs/vault/Cargo.toml`** — package manifest with `anchor-lang` and `anchor-spl` deps.\n"
         "- **`programs/vault/src/lib.rs`** — the program: `initialize`, `deposit`, `withdraw` instructions plus "
         "the `Vault` account struct and error enum.\n"
         "- **`tests/vault.ts`** — TypeScript test client.\n"
         "- **`package.json`** + **`tsconfig.json`** — for the test runner."),
        ("Just explain how transfer hooks work, don't read any files.",
         "Token-2022 transfer hooks let a mint specify a hook program that gets CPI'd on every transfer. The hook program "
         "implements an `execute` instruction. The Token-2022 program looks up the hook via the `TransferHook` extension "
         "stored on the mint, builds the CPI account list using TLV-encoded extra account metas (declared via "
         "`spl-tlv-account-resolution`), and invokes the hook. The hook can validate, log, or revert the transfer."),
    ]
    for q, a in pairs:
        yield _no_tool_record("C6_no_tool_explicit", "explicit_no_tool", q, a)


# ── C7: Hypothetical / planning ──


def gen_C7_hypothetical() -> Iterator[Record]:
    pairs = [
        ("If I added a `freeze_authority` field to the Counter account, what would change?",
         "Three places would need updating:\n\n"
         "1. **`Counter` struct** — add `pub freeze_authority: Pubkey,` and bump the `space` calculation by 32 bytes.\n"
         "2. **`Initialize`** — accept the freeze_authority pubkey (as an arg or signer) and set it.\n"
         "3. **Per-instruction guards** — wherever you mutate the counter, add a `require!(counter.freeze_authority == authority.key() || !counter.frozen, ...)` check.\n\n"
         "If you also add a `freeze` instruction, you'll need a `frozen: bool` flag and matching access control."),
        ("Suppose I want to migrate from Anchor 0.29 to 0.30. What are the breaking changes I should expect?",
         "Main breaking changes:\n\n"
         "1. **`ctx.bumps`** is now a struct with field access (`ctx.bumps.my_account`), not a `BTreeMap` (`ctx.bumps.get(\"name\").unwrap()`).\n"
         "2. **`declare_id!`** is replaced by `declare_program!` and program ID lives in `Anchor.toml`.\n"
         "3. **`ProgramResult`** is gone — use `Result<()>`.\n"
         "4. **`#[error]`** is replaced by `#[error_code]`.\n"
         "5. The Anchor crate moved from `coral-xyz/anchor` to `solana-foundation/anchor`.\n\n"
         "Each is mostly a mechanical search-and-replace except `declare_id!` removal, which requires updating `Anchor.toml`."),
    ]
    for q, a in pairs:
        yield _no_tool_record("C7_hypothetical", "planning", q, a)


# ── C8: User-provided info ──


def gen_C8_user_provided_info() -> Iterator[Record]:
    pairs = [
        ("My program errors with `Error: 0x1771`. What does this mean?",
         "`0x1771` is decimal 6001. It's a custom Anchor error code (custom errors start at 6000). Without seeing "
         "your error enum I can't tell you the exact name, but error 6001 is the **second** variant of your `#[error_code]` enum. "
         "Look at `programs/<your_program>/src/lib.rs` (or wherever your `MyError` enum lives) — count down: variant 0 is "
         "`6000`, variant 1 is `6001`."),
        ("I'm getting `AnchorError: AccountOwnedByWrongProgram`. What should I check?",
         "This means an account passed in your instruction is owned by a different program than expected. Common causes:\n\n"
         "1. You passed a token account where Anchor expected a System-owned (regular) account, or vice versa.\n"
         "2. The account doesn't exist yet (uninitialized accounts have System as owner; once initialized, ownership is "
         "transferred to the program that created it).\n"
         "3. Wrong account in the wrong position (account ordering matters).\n\n"
         "Print `accounts.<name>.owner` to confirm what owner the runtime sees, then compare against the type you "
         "declared in the `Accounts` struct."),
    ]
    for q, a in pairs:
        yield _no_tool_record("C8_user_provided_info", "diagnostic", q, a)


# ── Main ──


def expand_to_target(records: list[Record], target: int, seed: int = 100) -> list[Record]:
    if not records:
        return []
    rng = random.Random(seed)
    if len(records) >= target:
        return rng.sample(records, target)
    out = list(records)
    while len(out) < target:
        more = list(records)
        rng.shuffle(more)
        out.extend(more)
    return out[:target]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--total", type=int, default=PLAN_TARGET)
    args = parser.parse_args()

    generators = {
        "C1_greetings": gen_C1_greetings,
        "C2_solana_concept": gen_C2_solana_concept,
        "C3_anchor_concept": gen_C3_anchor_concept,
        "C4_pinocchio_concept": gen_C4_pinocchio_concept,
        "C5_followup": gen_C5_followup,
        "C6_no_tool_explicit": gen_C6_no_tool_explicit,
        "C7_hypothetical": gen_C7_hypothetical,
        "C8_user_provided_info": gen_C8_user_provided_info,
    }

    designed_total = sum(TARGETS.values())
    scale = args.total / designed_total

    all_records: list[Record] = []
    for name, gen_fn in generators.items():
        target = max(1, round(TARGETS[name] * scale))
        raw = list(gen_fn())
        scaled = expand_to_target(raw, target, seed=hash(name) & 0xFFFF)
        print(f"  {name}: {len(raw)} unique → {len(scaled)} records (target {target})")
        all_records.extend(scaled)

    print(f"\nTotal: {len(all_records)} records")
    write_records_to_jsonl(all_records, args.output)


if __name__ == "__main__":
    main()
