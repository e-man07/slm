"""V4 dataset — TRUE DIVERSITY, no over-repetition. Target ≥85% agent test.

Lessons learned:
  v2 (69%): grep tasks fail, discipline weak
  v3 (57%): regressed because 5 unique records expanded to 500 → overfit
  v4: every category MUST have ≥100 unique records; never repeat any record >10×

Composition (5K total v4 records):
  V4-A: Diverse grep                  (1500, 150+ unique)
  V4-B: Conversational reads          (800,  100+ unique)
  V4-C: Tool-choice discipline        (1000, 120+ unique)
  V4-D: Edit diversity                (700,  100+ unique)
  V4-E: Multi-step preservation       (1000, 120+ unique)

Trick: combinatorial expansion via (entity × pattern × phrasing) cross-products
gives 100s of unique records per category without repeating any record.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from _tool_calling_common import (
    build_messages,
    execute_tool_for_real,
    make_record,
    write_records_to_jsonl,
)
from gen_tool_fixtures import build_fixture
from schema import Record

OUTPUT_PATH = Path(__file__).resolve().parent / "sft_v4_targeted.jsonl"


# ── V4-A: Diverse grep examples (target: 1500 records, min 150 unique) ──
# v2 problem: model fakes grep output. Counter with MANY unique grep examples
# showing canonical pattern: <tool_call> → <tool_result> → summary.

def gen_grep_v4():
    """Target: 1500 records, ~200 unique."""
    grep_targets = []
    # Per-fixture pattern lists (50+ unique pairs)
    patterns_per_fixture = {
        "anchor_counter": ["#\\[program\\]", "ctx\\.bumps", "Result<\\(\\)>", "pub fn", "#\\[account\\]",
                           "Pubkey", "Signer", "init", "seeds", "bump", "Account", "Context", "u64",
                           "use anchor_lang", "msg!", "checked_add", "ErrorCode", "Counter", "MyAccount"],
        "anchor_vault": ["use anchor_spl", "Transfer", "transfer", "TokenAccount", "CpiContext",
                         "#\\[error_code\\]", "InsufficientBalance", "Token", "Vault", "deposit"],
        "anchor_buggy": ["ctx\\.bumps\\.get", "unwrap", "profile", "Profile", "init"],
        "anchor_legacy": ["declare_id!", "ProgramResult", "legacy", "Data", "value"],
        "multi_workspace": ["#\\[program\\]", "Pubkey", "Signer", "Account", "has_one", "init",
                            "Escrow", "PriceFeed", "amount", "maker", "authority", "price"],
        "native_solana": ["entrypoint!", "process_instruction", "AccountInfo", "BorshSerialize",
                          "borsh", "msg!", "CounterAccount", "ProgramResult"],
        "pinocchio": ["pinocchio", "AccountInfo", "ProgramResult", "Pubkey", "wrapping_add"],
    }
    for fx_name, patterns in patterns_per_fixture.items():
        for p in patterns:
            grep_targets.append((fx_name, p))

    # Many phrasings (20+) — combine each (fixture, pattern) with these
    phrasings = [
        "Search for `{p}` in {fx}.",
        "Find references to `{p}` in {fx}.",
        "Where is `{p}` used in {fx}?",
        "Look for `{p}` in {fx}.",
        "Grep for `{p}` in {fx}.",
        "Hunt for `{p}` across {fx}.",
        "Scan {fx} for `{p}`.",
        "Find all occurrences of `{p}` in {fx}.",
        "Tell me where `{p}` appears in {fx}.",
        "Locate `{p}` in {fx}.",
        "Search the {fx} codebase for `{p}`.",
        "Could you find `{p}` in {fx} for me?",
        "I need to find `{p}` in {fx}.",
        "Help me locate `{p}` in {fx}.",
        "Where does `{p}` show up in {fx}?",
        "Show me `{p}` references in {fx}.",
        "Trace `{p}` through {fx}.",
        "Find `{p}` matches in {fx}.",
    ]

    rng = random.Random(401)
    seen_records = set()
    out_records = []

    for fx_name, pattern in grep_targets:
        with build_fixture(fx_name) as fx:
            result = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
            if not result.success:
                continue

            friendly = pattern.replace("\\", "")
            # Use a different subset of phrasings per (fixture, pattern) to ensure diversity
            chosen_phrasings = rng.sample(phrasings, k=min(8, len(phrasings)))

            for phrasing in chosen_phrasings:
                user_msg = phrasing.format(p=friendly, fx=fx_name)

                if "No matches" in result.output:
                    final = f"No matches for `{friendly}` in {fx_name}."
                else:
                    line_count = result.output.count("\n") + 1
                    final = f"Found {line_count} match(es) for `{friendly}` in {fx_name} — see output above."

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Searching with grep_files.", [("grep_files", {"pattern": pattern})])),
                        ("user", [("grep_files", True, result.output)]),
                    ],
                    final=final,
                )
                rec = make_record(messages, "V4A_grep", subcategory=fx_name)
                if rec.id not in seen_records:
                    seen_records.add(rec.id)
                    out_records.append(rec)

    return out_records


# ── V4-B: Conversational reads (target: 800, min 100 unique) ──

def gen_conversational_reads_v4():
    """20+ files × 15 phrasings = 300+ unique."""
    file_targets = [
        ("anchor_counter", "Anchor.toml"),
        ("anchor_counter", "Cargo.toml"),
        ("anchor_counter", "programs/counter/src/lib.rs"),
        ("anchor_counter", "programs/counter/Cargo.toml"),
        ("anchor_counter", "tests/counter.ts"),
        ("anchor_counter", "package.json"),
        ("anchor_counter", "tsconfig.json"),
        ("anchor_counter", "README.md"),
        ("anchor_vault", "programs/vault/src/lib.rs"),
        ("anchor_vault", "programs/vault/src/state.rs"),
        ("anchor_vault", "programs/vault/src/errors.rs"),
        ("anchor_vault", "programs/vault/Cargo.toml"),
        ("anchor_vault", "Anchor.toml"),
        ("multi_workspace", "Anchor.toml"),
        ("multi_workspace", "Cargo.toml"),
        ("multi_workspace", "programs/escrow/src/lib.rs"),
        ("multi_workspace", "programs/escrow/Cargo.toml"),
        ("multi_workspace", "programs/oracle/src/lib.rs"),
        ("multi_workspace", "programs/oracle/Cargo.toml"),
        ("anchor_buggy", "programs/buggy/src/lib.rs"),
        ("anchor_legacy", "programs/legacy/src/lib.rs"),
        ("native_solana", "src/lib.rs"),
        ("native_solana", "Cargo.toml"),
        ("pinocchio", "src/lib.rs"),
        ("pinocchio", "Cargo.toml"),
    ]

    phrasings = [
        "Show me the contents of {path}.",
        "What's in {path}?",
        "Display {path}.",
        "Open {path} for me.",
        "View {path}.",
        "I want to see {path}.",
        "Print {path}.",
        "What does {path} contain?",
        "Read {path}.",
        "Look at {path}.",
        "Pull up {path}.",
        "Bring up {path}.",
        "Could you show me {path}?",
        "Help me see {path}.",
        "Cat {path}.",
        "Let me check {path}.",
        "What's inside {path}?",
        "Show me what's in {path}.",
        "I need to see {path}.",
        "Read me {path}.",
    ]

    rng = random.Random(402)
    seen_records = set()
    out_records = []

    for fx_name, rel_path in file_targets:
        with build_fixture(fx_name) as fx:
            result = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            if not result.success:
                continue
            chosen = rng.sample(phrasings, k=min(12, len(phrasings)))
            for phrasing in chosen:
                user_msg = phrasing.format(path=rel_path)
                final = f"Showing `{rel_path}` (see contents above)."
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Reading the file.", [("read_file", {"path": rel_path})])),
                        ("user", [("read_file", True, result.output)]),
                    ],
                    final=final,
                )
                rec = make_record(messages, "V4B_conversational_read", subcategory=fx_name)
                if rec.id not in seen_records:
                    seen_records.add(rec.id)
                    out_records.append(rec)

    return out_records


# ── V4-C: Tool-choice discipline (target: 1000, min 120 unique) ──

def gen_discipline_v4():
    rng = random.Random(403)
    seen = set()
    out = []

    # J1: read_file over cat - many file targets
    file_targets = [
        ("anchor_counter", "Anchor.toml"),
        ("anchor_counter", "programs/counter/src/lib.rs"),
        ("anchor_counter", "tests/counter.ts"),
        ("anchor_counter", "Cargo.toml"),
        ("anchor_counter", "package.json"),
        ("anchor_vault", "programs/vault/src/lib.rs"),
        ("anchor_vault", "programs/vault/src/state.rs"),
        ("multi_workspace", "programs/escrow/src/lib.rs"),
        ("multi_workspace", "programs/oracle/src/lib.rs"),
        ("multi_workspace", "Anchor.toml"),
    ]
    read_phrasings = [
        "Show me {path}.",
        "What's in {path}?",
        "Display {path}.",
        "Read me {path}.",
        "Cat {path}.",
        "View {path}.",
        "Print {path}.",
        "Could you display {path}?",
    ]
    for fx_name, rel_path in file_targets:
        with build_fixture(fx_name) as fx:
            result = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            if not result.success:
                continue
            for phrasing in read_phrasings:
                user_msg = phrasing.format(path=rel_path)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Using read_file (preferred over cat).", [("read_file", {"path": rel_path})])),
                        ("user", [("read_file", True, result.output)]),
                    ],
                    final=f"`{rel_path}` shown above.",
                )
                rec = make_record(messages, "V4C_disc_read", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # J2/J3: glob over find/ls
    glob_targets = [
        ("anchor_counter", "**/*.rs", "."),
        ("anchor_counter", "**/*.toml", "."),
        ("anchor_counter", "**/*.ts", "."),
        ("multi_workspace", "**/*.rs", "."),
        ("multi_workspace", "programs/**/lib.rs", "."),
        ("multi_workspace", "**/Cargo.toml", "."),
        ("anchor_vault", "**/*.rs", "."),
        ("native_solana", "**/*.rs", "."),
    ]
    glob_phrasings = [
        "Find all {pat} files.",
        "List every {pat} file.",
        "Where are the {pat} files?",
        "Show me {pat} files.",
        "Locate all {pat} files.",
        "Browse {pat} files.",
        "ls -name '{pat}'",
        "Find {pat} files in this project.",
    ]
    for fx_name, pattern, search_path in glob_targets:
        with build_fixture(fx_name) as fx:
            result = execute_tool_for_real("glob_files", {"pattern": pattern}, fx.path)
            if not result.success:
                continue
            for phrasing in glob_phrasings:
                user_msg = phrasing.format(pat=pattern)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Using glob_files (preferred over find).", [("glob_files", {"pattern": pattern})])),
                        ("user", [("glob_files", True, result.output)]),
                    ],
                    final="Files listed above.",
                )
                rec = make_record(messages, "V4C_disc_glob", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # J4: grep over grep CLI
    grep_targets = [
        ("anchor_counter", "Pubkey"),
        ("anchor_counter", "ctx\\.bumps"),
        ("anchor_counter", "checked_add"),
        ("anchor_legacy", "declare_id"),
        ("anchor_buggy", "unwrap"),
        ("multi_workspace", "Pubkey"),
        ("multi_workspace", "has_one"),
    ]
    grep_disc_phrasings = [
        "Search for `{pat}`.",
        "Find `{pat}` in the source.",
        "rg '{pat}'",
        "grep -r {pat} .",
        "Where is `{pat}` used?",
        "Look for `{pat}`.",
    ]
    for fx_name, pat in grep_targets:
        with build_fixture(fx_name) as fx:
            result = execute_tool_for_real("grep_files", {"pattern": pat}, fx.path)
            if not result.success:
                continue
            friendly = pat.replace("\\", "")
            for phrasing in grep_disc_phrasings:
                user_msg = phrasing.format(pat=friendly)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Using grep_files (preferred over grep).", [("grep_files", {"pattern": pat})])),
                        ("user", [("grep_files", True, result.output)]),
                    ],
                    final="Search complete.",
                )
                rec = make_record(messages, "V4C_disc_grep", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # J7: legitimate Bash usage
    bash_cases = [
        ("Build the program.", "anchor build", "Compiling counter\nFinished `release` profile in 12.4s"),
        ("Run the tests.", "anchor test", "  counter\n    ✓ initialize (245ms)\n  1 passing (2s)"),
        ("Show git status.", "git status", "On branch main\nnothing to commit, working tree clean"),
        ("Check anchor version.", "anchor --version", "anchor-cli 0.30.1"),
        ("Run cargo check.", "cargo check", "Checking counter v0.1.0\nFinished in 4.2s"),
        ("Format with cargo fmt.", "cargo fmt", "(no output)"),
        ("List git log.", "git log --oneline -5", "abc1234 Add increment\ndef5678 Initial counter"),
        ("Run cargo build release.", "cargo build --release", "Compiling counter\nFinished in 8.3s"),
        ("Show solana version.", "solana --version", "solana-cli 1.18.1"),
        ("Run npm install.", "npm install", "added 142 packages in 5s"),
    ]
    for prompt, cmd, output in bash_cases:
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Running `{cmd}` (Bash is the right tool here).", [("run_command", {"command": cmd})])),
                ("user", [("run_command", True, output)]),
            ],
            final=f"`{cmd}` completed.",
        )
        rec = make_record(messages, "V4C_legit_bash", subcategory=cmd.split()[0])
        if rec.id not in seen:
            seen.add(rec.id)
            out.append(rec)

    return out


# ── V4-D: Edit diversity (target: 700, min 100 unique) ──

def gen_edit_diversity_v4():
    rng = random.Random(404)
    seen = set()
    out = []

    edit_specs = [
        # (fixture, file, old_text, new_text)
        ("anchor_counter", "programs/counter/src/lib.rs",
         "ctx.accounts.counter.count = 0;", "ctx.accounts.counter.count = 1;"),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "pub count: u64,", "pub count: u128,"),
        ("anchor_counter", "programs/counter/src/lib.rs",
         '#[msg("Counter overflow")]', '#[msg("Counter has overflowed u64::MAX")]'),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "space = 8 + 8 + 32 + 1", "space = 8 + 16 + 32 + 1"),
        ("anchor_counter", "Cargo.toml",
         'name = "counter"', 'name = "mycounter"'),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         '*ctx.bumps.get("profile").unwrap()', "ctx.bumps.profile"),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "pub bump: u8,", "pub bump: u8,\n    pub created_at: i64,"),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "ProgramResult", "Result<()>"),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         'declare_id!("Fg6PaFpoGXkKXx2KcD684s5rJNHHk3JG462ZiJxkZuFZ");',
         "// Program ID is set in Anchor.toml"),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {",
         "pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {\n        require!(amount > 0, VaultError::InsufficientBalance);"),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         "pub amount: u64,", "pub amount: u64,\n    pub created_at: i64,"),
        ("multi_workspace", "programs/oracle/src/lib.rs",
         "pub price: u64,", "pub price: u64,\n    pub last_block: u64,"),
    ]

    edit_phrasings = [
        "In `{path}`, change `{old}` to `{new}`.",
        "Update `{old}` to `{new}` in `{path}`.",
        "Replace `{old}` with `{new}` in {path}.",
        "Edit {path}: change `{old}` → `{new}`.",
        "Modify `{path}`: replace `{old}` with `{new}`.",
        "In {path}, swap `{old}` for `{new}`.",
        "Update {path} so that `{old}` becomes `{new}`.",
    ]

    for fx_name, rel_path, old_t, new_t in edit_specs:
        with build_fixture(fx_name) as fx:
            result = execute_tool_for_real("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t}, fx.path)
            if not result.success:
                continue
            old_short = old_t.split("\n")[0][:50]
            new_short = new_t.split("\n")[0][:50]
            for phrasing in edit_phrasings:
                user_msg = phrasing.format(path=rel_path, old=old_short, new=new_short)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Editing the file.", [("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t})])),
                        ("user", [("edit_file", True, result.output)]),
                    ],
                    final=f"Edit applied to `{rel_path}`.",
                )
                rec = make_record(messages, "V4D_edit", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    return out


# ── V4-E: Multi-step preservation (target: 1000, min 120 unique) ──
# Critical: v3 broke multi-step. Keep multi-step examples diverse and plentiful.

def gen_multistep_v4():
    rng = random.Random(405)
    seen = set()
    out = []

    # Pattern A: read → final answer (with substantive analysis)
    # Expanded to many (fixture, file, prompt, final) combos with phrasing variations
    read_then_explain = [
        ("anchor_counter", "programs/counter/src/lib.rs",
         "What does the counter program do?",
         "It's an Anchor program with `initialize` (creates a counter PDA) and `increment` (bumps count with overflow check). PDA seed: `[\"counter\", user_pubkey]`."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "Walk me through the counter logic.",
         "The counter has two instructions: initialize sets count=0 and stores the bump; increment uses checked_add for overflow safety and validates the authority via has_one."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "Summarize the structure of this Anchor program.",
         "It defines a `Counter` account holding `count: u64`, `authority: Pubkey`, and `bump: u8`. Two instructions exposed via `#[program]`: initialize and increment."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "Does this program use checked arithmetic?",
         "Yes — `increment` uses `checked_add(1)` and returns `CounterOverflow` on failure rather than wrapping silently."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "How is the counter PDA derived?",
         "Seeds are `[b\"counter\", user.key().as_ref()]`. The bump is stored on the account so subsequent calls don't have to recompute it."),
        ("anchor_counter", "Anchor.toml",
         "What programs are configured here?",
         "One program — `counter` — with the program ID declared and `[programs.localnet]` pointing at the same address."),
        ("anchor_counter", "Cargo.toml",
         "Describe the workspace layout.",
         "Workspace root with `programs/*` as members. The counter program is the only crate."),
        ("anchor_counter", "tests/counter.ts",
         "Walk me through the test.",
         "Loads the program, derives the counter PDA, calls `initialize`, then calls `increment` and asserts `count == 1`."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "Explain the vault program.",
         "Single-instruction vault: `deposit` CPIs into the SPL Token program to transfer tokens from the user's account to the vault."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "How does the vault handle token transfers?",
         "Uses `anchor_spl::token::transfer` with a `CpiContext` whose authority is the depositor. The vault account is just a destination token account."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "Does the deposit validate the amount?",
         "It returns `VaultError::InsufficientBalance` if `amount == 0`. No upper bound check."),
        ("anchor_vault", "programs/vault/src/state.rs",
         "What account state does the vault track?",
         "A `Vault` account storing `authority`, `token_account`, and a `bump`. Initialized once per authority."),
        ("anchor_vault", "programs/vault/src/errors.rs",
         "List the vault error codes.",
         "Two: `InsufficientBalance` (deposit of zero or below-min amount) and `Unauthorized` (caller mismatch)."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "Review this code for issues.",
         "Found one issue: line 8 uses `*ctx.bumps.get(\"profile\").unwrap()` which is the deprecated Anchor 0.29 pattern. Use `ctx.bumps.profile` instead."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "Are there any deprecation warnings I should worry about?",
         "Yes — the bump access uses `ctx.bumps.get(\"profile\").unwrap()` which is removed in Anchor 0.30. Migrate to direct field access: `ctx.bumps.profile`."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "Why might this program fail to compile on Anchor 0.30?",
         "`ctx.bumps` is now a struct, not a HashMap. The `.get(\"profile\")` call won't compile. Replace with `ctx.bumps.profile`."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "What's wrong with this program?",
         "Two deprecated patterns: `declare_id!` macro (use Anchor.toml instead) and `ProgramResult` return type (use `Result<()>` instead)."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "Modernize this program — what would you change?",
         "Replace `ProgramResult` with `Result<()>`, drop `declare_id!` in favor of Anchor.toml configuration, and update any 0.x-style account validation to current attribute syntax."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "Is this Anchor program current?",
         "No — it uses `ProgramResult` (deprecated) and inlined `declare_id!`. Modern Anchor uses `Result<()>` and reads the program ID from Anchor.toml."),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         "What does the escrow do?",
         "Stores escrow metadata (amount + maker pubkey) in a PDA seeded by [\"escrow\", maker_pubkey]. No actual asset transfer logic — just state initialization."),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         "Is the escrow safe to use as-is?",
         "Not for production — it tracks `amount` and `maker` but never transfers assets. You'd need to add deposit/withdraw CPIs into a token program before this is functional."),
        ("multi_workspace", "programs/oracle/src/lib.rs",
         "Explain the oracle program.",
         "An authority-gated price feed. `update` lets the authority set price + timestamp on a PriceFeed account. Uses `has_one = authority` for access control."),
        ("multi_workspace", "programs/oracle/src/lib.rs",
         "Who can update the oracle price?",
         "Only the account stored in `PriceFeed.authority`. The instruction uses `has_one = authority` so a mismatched signer fails with `ConstraintHasOne`."),
        ("multi_workspace", "programs/oracle/src/lib.rs",
         "Does this oracle use any decay or staleness check?",
         "No — it stores the latest `price` and `last_updated` timestamp but consumers must enforce staleness themselves. There's no on-chain rejection of old data."),
        ("multi_workspace", "Anchor.toml",
         "How many programs are in this workspace?",
         "Two: `escrow` and `oracle`, each with its own program ID under `[programs.localnet]`."),
        ("multi_workspace", "Cargo.toml",
         "Describe the cargo workspace.",
         "Root workspace with both `programs/escrow` and `programs/oracle` as members. Anchor and SPL token are shared dependencies."),
        ("native_solana", "src/lib.rs",
         "Describe this native Solana program.",
         "Native (no Anchor): defines `CounterAccount` with Borsh serialization, increments count on every invocation. No overflow protection — `count += 1` would wrap silently."),
        ("native_solana", "src/lib.rs",
         "Compare this with an Anchor counter.",
         "Same logical behavior but no `#[program]`/`#[account]` macros — manual `entrypoint!` plus Borsh serialization. Anchor would handle account validation and (de)serialization automatically."),
        ("native_solana", "src/lib.rs",
         "What's missing here from a safety standpoint?",
         "Three things: no overflow check on `count += 1`, no signer/authority validation, and no account-owner verification before deserializing."),
        ("pinocchio", "src/lib.rs",
         "What does this Pinocchio program do?",
         "A minimal Pinocchio counter — uses `wrapping_add` for the bump rather than `checked_add`. Pinocchio is the no-stdlib SDK for ultra-low-CU programs."),
        ("pinocchio", "src/lib.rs",
         "Why use Pinocchio over Anchor here?",
         "Pinocchio targets minimal compute-unit budgets — no SDK allocations, no SystemProgram CPI sugar. Useful when you need every CU."),
        ("pinocchio", "Cargo.toml",
         "What dependencies does this Pinocchio crate use?",
         "Just `pinocchio` itself with `cdylib` crate-type. No `solana-program` or `anchor-lang` — that's the whole point."),
    ]
    explain_phrasings = [
        "{prompt}",
        "Read {path} and answer: {prompt}",
        "Open {path}, then: {prompt}",
        "Take a look at {path} — {prompt}",
    ]
    for fx_name, path, prompt, final in read_then_explain:
        with build_fixture(fx_name) as fx:
            result = execute_tool_for_real("read_file", {"path": path}, fx.path)
            if not result.success:
                continue
            for tmpl in explain_phrasings:
                user_msg = tmpl.format(prompt=prompt, path=path)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Reading the file.", [("read_file", {"path": path})])),
                        ("user", [("read_file", True, result.output)]),
                    ],
                    final=final,
                )
                rec = make_record(messages, "V4E_read_explain", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # Pattern B: grep → read → final (expanded)
    grep_read = [
        ("anchor_counter", "#\\[program\\]",
         "Find the program module and tell me what's in it.",
         "Found `#[program]` in `programs/counter/src/lib.rs`. The module contains `initialize` and `increment` instructions."),
        ("anchor_counter", "#\\[account\\]",
         "Locate the account struct and describe it.",
         "Found `#[account]` on the `Counter` struct in `programs/counter/src/lib.rs`. Holds `count: u64`, `authority: Pubkey`, and `bump: u8`."),
        ("anchor_counter", "checked_add",
         "Where is checked_add used?",
         "In `programs/counter/src/lib.rs` inside `increment` — `count.checked_add(1)` with overflow returning `CounterOverflow`."),
        ("anchor_counter", "ctx\\.bumps",
         "How does the program access bumps?",
         "In `programs/counter/src/lib.rs` — uses `ctx.bumps.counter` directly (modern Anchor 0.30+ syntax)."),
        ("multi_workspace", "#\\[program\\]",
         "Locate all program modules in this workspace.",
         "Two program modules: escrow (in `programs/escrow/src/lib.rs`) and oracle (in `programs/oracle/src/lib.rs`)."),
        ("multi_workspace", "has_one",
         "Find any has_one constraints.",
         "Found `has_one = authority` in `programs/oracle/src/lib.rs` — gates `update` on the stored authority pubkey."),
        ("multi_workspace", "#\\[account\\]",
         "List all account structs across the workspace.",
         "Two account types: `Escrow` in `programs/escrow/src/lib.rs` and `PriceFeed` in `programs/oracle/src/lib.rs`."),
        ("anchor_legacy", "declare_id!",
         "Find the declare_id! call and read the file.",
         "`declare_id!` is in `programs/legacy/src/lib.rs`. The program also uses the deprecated `ProgramResult` return type."),
        ("anchor_legacy", "ProgramResult",
         "Find any usages of the deprecated ProgramResult type.",
         "Found in `programs/legacy/src/lib.rs` — both functions return `ProgramResult`. Modern Anchor uses `Result<()>`."),
        ("anchor_buggy", "ctx\\.bumps\\.get",
         "Find any uses of the deprecated bump pattern.",
         "Found one in `programs/buggy/src/lib.rs` — uses `*ctx.bumps.get(\"profile\").unwrap()`. Modern equivalent: `ctx.bumps.profile`."),
        ("anchor_buggy", "unwrap",
         "Find unwrap() calls — they're a code smell on-chain.",
         "Found in `programs/buggy/src/lib.rs` on the bump access. Replace with field access; never unwrap on-chain in error paths."),
        ("anchor_vault", "Transfer",
         "Find SPL token Transfer usage.",
         "In `programs/vault/src/lib.rs` — `anchor_spl::token::Transfer` accounts struct populated for the deposit CPI."),
        ("anchor_vault", "CpiContext",
         "Find CPI invocations.",
         "Found in `programs/vault/src/lib.rs` — `CpiContext::new` wrapping the SPL token program for `transfer`."),
        ("native_solana", "entrypoint!",
         "Find the program entrypoint.",
         "In `src/lib.rs` — `entrypoint!(process_instruction)` declares the on-chain entrypoint."),
        ("native_solana", "BorshSerialize",
         "Find Borsh-serialized state.",
         "In `src/lib.rs` — the `CounterAccount` derives `BorshSerialize`/`BorshDeserialize` for state encoding."),
        ("pinocchio", "wrapping_add",
         "Find any wrapping arithmetic.",
         "In `src/lib.rs` — counter increment uses `wrapping_add(1)`. Be aware this silently wraps; consider checked_add if overflow matters."),
    ]
    for fx_name, pattern, prompt, final in grep_read:
        with build_fixture(fx_name) as fx:
            grep_r = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
            if not grep_r.success or "No matches" in grep_r.output:
                continue
            first_line = grep_r.output.split("\n")[0]
            match_file = first_line.split(":")[0] if ":" in first_line else None
            if not match_file or not (fx.path / match_file).exists():
                continue
            read_r = execute_tool_for_real("read_file", {"path": match_file}, fx.path)
            if not read_r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Searching first.", [("grep_files", {"pattern": pattern})])),
                    ("user", [("grep_files", True, grep_r.output)]),
                    ("assistant", (f"Reading {match_file}.", [("read_file", {"path": match_file})])),
                    ("user", [("read_file", True, read_r.output)]),
                ],
                final=final,
            )
            rec = make_record(messages, "V4E_grep_read", subcategory=fx_name)
            if rec.id not in seen:
                seen.add(rec.id)
                out.append(rec)

    # Pattern C: glob → read multiple → summarize (expanded)
    glob_multi_read = [
        ("multi_workspace", "**/lib.rs",
         "Compare all the programs in this workspace.",
         "Two programs: **escrow** (PDA-based metadata storage) and **oracle** (authority-gated price feed). Escrow uses PDA seeds for ownership; oracle uses has_one for access control."),
        ("multi_workspace", "**/lib.rs",
         "List the programs and their entry points.",
         "Both `programs/escrow/src/lib.rs` and `programs/oracle/src/lib.rs` use `#[program]`. Escrow exposes `initialize`; oracle exposes `update`."),
        ("multi_workspace", "**/Cargo.toml",
         "Compare the cargo manifests in this workspace.",
         "Found three Cargo.toml files: workspace root plus one per program. Both program crates depend on `anchor-lang`; escrow has no extra deps, oracle is similar."),
        ("anchor_counter", "**/*.rs",
         "List all Rust files and tell me which one defines the program.",
         "Only one Rust file: `programs/counter/src/lib.rs`. That's where `#[program]` lives."),
        ("anchor_vault", "**/*.rs",
         "Walk through every Rust file in the vault crate.",
         "Three files: `lib.rs` (program entrypoint and `deposit`), `state.rs` (Vault account struct), and `errors.rs` (VaultError enum)."),
        ("multi_workspace", "**/lib.rs",
         "Which program in this workspace has access control?",
         "The oracle (`programs/oracle/src/lib.rs`) — it gates `update` on `has_one = authority`. Escrow has no access control beyond PDA derivation."),
    ]
    for fx_name, pattern, prompt, final in glob_multi_read:
        with build_fixture(fx_name) as fx:
            glob_r = execute_tool_for_real("glob_files", {"pattern": pattern}, fx.path)
            if not glob_r.success:
                continue
            files = [ln.strip() for ln in glob_r.output.split("\n") if ln.strip().endswith(".rs")]
            files = [f for f in files if (fx.path / f).is_file()][:2]
            if len(files) < 2:
                continue

            traj = [
                ("assistant", ("Finding the files.", [("glob_files", {"pattern": pattern})])),
                ("user", [("glob_files", True, glob_r.output)]),
            ]
            for fpath in files:
                rr = execute_tool_for_real("read_file", {"path": fpath}, fx.path)
                if rr.success:
                    traj.append(("assistant", (f"Reading {fpath}.", [("read_file", {"path": fpath})])))
                    traj.append(("user", [("read_file", True, rr.output)]))
            messages = build_messages(user_msg=prompt, trajectory=traj, final=final)
            rec = make_record(messages, "V4E_glob_multi_read", subcategory=fx_name)
            if rec.id not in seen:
                seen.add(rec.id)
                out.append(rec)

    # Pattern D: read → edit → run (verify build) — expanded
    read_edit_run = [
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         '*ctx.bumps.get("profile").unwrap()', "ctx.bumps.profile",
         "cargo check", "Checking buggy v0.1.0\nFinished in 4.1s",
         "Fix the deprecated bump pattern and verify with cargo check.",
         "Replaced the deprecated form. cargo check passes."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         '*ctx.bumps.get("profile").unwrap()', "ctx.bumps.profile",
         "anchor build", "Compiling buggy v0.1.0\nFinished `release` profile in 11.8s",
         "Migrate the bump access to Anchor 0.30 syntax and run anchor build.",
         "Migrated. anchor build succeeds in release mode."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "ProgramResult", "Result<()>",
         "cargo check", "Checking legacy v0.1.0\nFinished in 3.4s",
         "Update the return type to modern Result<()> and verify.",
         "Updated. Build succeeds."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "ProgramResult", "Result<()>",
         "anchor build", "Compiling legacy v0.1.0\nFinished `release` profile in 9.2s",
         "Modernize the return type and run anchor build.",
         "Done. anchor build succeeds."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "pub count: u64,", "pub count: u128,",
         "cargo check", "Checking counter v0.1.0\nFinished in 4.6s",
         "Widen the counter to u128 and verify it still compiles.",
         "Widened to u128. cargo check is clean."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "pub count: u64,", "pub count: u128,",
         "cargo build", "Compiling counter v0.1.0\nFinished `dev` profile in 5.4s",
         "Change count to u128 and run cargo build.",
         "Built successfully with the wider integer."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {",
         "pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {\n        require!(amount > 0, VaultError::InsufficientBalance);",
         "cargo check", "Checking vault v0.1.0\nFinished in 5.1s",
         "Add an amount-zero guard to deposit and verify.",
         "Added the require!. cargo check passes."),
    ]
    for fx_name, path, old_t, new_t, cmd, cmd_out, prompt, final in read_edit_run:
        with build_fixture(fx_name) as fx:
            read_r = execute_tool_for_real("read_file", {"path": path}, fx.path)
            edit_r = execute_tool_for_real("edit_file", {"path": path, "old_text": old_t, "new_text": new_t}, fx.path)
            if not (read_r.success and edit_r.success):
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading first.", [("read_file", {"path": path})])),
                    ("user", [("read_file", True, read_r.output)]),
                    ("assistant", ("Applying the fix.", [("edit_file", {"path": path, "old_text": old_t, "new_text": new_t})])),
                    ("user", [("edit_file", True, edit_r.output)]),
                    ("assistant", ("Verifying with cargo check.", [("run_command", {"command": cmd})])),
                    ("user", [("run_command", True, cmd_out)]),
                ],
                final=final,
            )
            rec = make_record(messages, "V4E_read_edit_run", subcategory=fx_name)
            if rec.id not in seen:
                seen.add(rec.id)
                out.append(rec)

    # Pattern E: parallel reads (multiple files in one assistant turn) — expanded
    parallel_reads = [
        ("multi_workspace", ["programs/escrow/src/lib.rs", "programs/oracle/src/lib.rs"],
         "Read both program files at once and tell me which has authority gating.",
         "The oracle uses `has_one = authority` for access control on `update`. Escrow uses only PDA seeds for ownership."),
        ("multi_workspace", ["programs/escrow/src/lib.rs", "programs/oracle/src/lib.rs"],
         "Read both programs and compare their account structures.",
         "Escrow's account stores `amount` and `maker`. Oracle's `PriceFeed` stores `authority`, `price`, and `last_updated`."),
        ("multi_workspace", ["programs/escrow/Cargo.toml", "programs/oracle/Cargo.toml"],
         "Compare the two crate manifests in this workspace.",
         "Both depend on `anchor-lang`; neither pulls extra deps. Names differ (`escrow` vs `oracle`) but versions match."),
        ("multi_workspace", ["Anchor.toml", "Cargo.toml"],
         "Read the workspace manifests and tell me how programs are wired in.",
         "`Anchor.toml` lists program IDs under `[programs.localnet]`; `Cargo.toml` declares both program crates as workspace members."),
        ("anchor_counter", ["Anchor.toml", "Cargo.toml"],
         "Read both manifests so I can compare them.",
         "`Anchor.toml` has the program ID and cluster config. `Cargo.toml` declares the workspace members."),
        ("anchor_counter", ["programs/counter/src/lib.rs", "tests/counter.ts"],
         "Read the program and its test side by side.",
         "The on-chain program exposes `initialize` and `increment`; the test calls both and asserts the counter advances by 1."),
        ("anchor_counter", ["programs/counter/Cargo.toml", "Cargo.toml"],
         "Read the program crate manifest and the workspace manifest.",
         "Workspace declares `programs/*` as members; the program crate declares anchor-lang as the only direct dep."),
        ("anchor_vault", ["programs/vault/src/lib.rs", "programs/vault/src/state.rs"],
         "Read the vault program and its state module together.",
         "lib.rs holds the `deposit` instruction; state.rs holds the `Vault` account struct (authority + token_account + bump)."),
        ("anchor_vault", ["programs/vault/src/lib.rs", "programs/vault/src/errors.rs"],
         "Read the vault program and the errors module.",
         "lib.rs returns `VaultError::InsufficientBalance` for zero deposits — the variant is defined in errors.rs alongside `Unauthorized`."),
        ("anchor_vault", ["programs/vault/src/state.rs", "programs/vault/src/errors.rs"],
         "Read the state and error modules together.",
         "State defines the `Vault` PDA with three fields. Errors defines `InsufficientBalance` and `Unauthorized` — used together in deposit/withdraw checks."),
    ]
    for fx_name, files, prompt, final in parallel_reads:
        with build_fixture(fx_name) as fx:
            calls = []
            results = []
            for f in files:
                rr = execute_tool_for_real("read_file", {"path": f}, fx.path)
                if rr.success:
                    calls.append(("read_file", {"path": f}))
                    results.append(("read_file", True, rr.output))
            if len(calls) < 2:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[("assistant", ("Reading both in parallel.", calls)), ("user", results)],
                final=final,
            )
            rec = make_record(messages, "V4E_parallel_reads", subcategory=fx_name)
            if rec.id not in seen:
                seen.add(rec.id)
                out.append(rec)

    return out


# ── Main ──

def expand_to_target_capped(records, target, max_rep=10, seed=42):
    """Expand records but cap repetition at max_rep× to prevent overfit."""
    if not records:
        return []
    rng = random.Random(seed)
    if len(records) >= target:
        return rng.sample(records, target)
    max_total = len(records) * max_rep
    real_target = min(target, max_total)
    if real_target < target:
        print(f"  WARNING: only {len(records)} unique records, capped at {max_rep}× = {real_target} (target was {target})")
    out = list(records)
    while len(out) < real_target:
        more = list(records)
        rng.shuffle(more)
        out.extend(more)
    return out[:real_target]


def main():
    targets = {
        "V4A_grep": (gen_grep_v4, 1500),
        "V4B_conv_read": (gen_conversational_reads_v4, 800),
        "V4C_discipline": (gen_discipline_v4, 1000),
        "V4D_edit": (gen_edit_diversity_v4, 700),
        "V4E_multistep": (gen_multistep_v4, 1000),
    }

    all_records = []
    for name, (gen_fn, target) in targets.items():
        raw = list(gen_fn())
        scaled = expand_to_target_capped(raw, target, max_rep=10, seed=hash(name) & 0xFFFF)
        ratio = f"{target/len(raw):.1f}×" if raw else "N/A"
        print(f"  {name}: {len(raw)} unique → {len(scaled)} records (target {target}, repetition {ratio})")
        all_records.extend(scaled)

    print(f"\nTotal V4 records: {len(all_records)}")
    write_records_to_jsonl(all_records, OUTPUT_PATH)


if __name__ == "__main__":
    main()
