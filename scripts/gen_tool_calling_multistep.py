"""Groups B + F: Multi-step trajectories and Solana agent tasks (target: 3,200).

These records have 3+ iterations: assistant calls a tool → result → another
tool → result → ... → final answer. They teach the model how to chain tools
to accomplish realistic engineering tasks.

Subcategories:
  B1  read → final answer                       (400)
  B2  grep → read → final                       (350)
  B3  glob → read → summarize                   (250)
  B4  read → edit → final                       (400)
  B5  read → edit → run (cargo check) → final   (300)
  B6  write → run → final                       (200)
  B7  grep → read → edit → run → final          (250)
  B8  glob → read multiple → final              (200)
  B9  run (find error) → grep → read → edit → run (verify) (150)
  B10 Parallel multi-tool single turn           (200)

  F1  Build counter program e2e                 (200)
  F2  Find PDA bug                              (150)
  F3  Reentrancy audit (no tool reasoning)      (100)
  F4  Add InitSpace to struct                   (100)
  F5  Migrate declare_id! → declare_program!    (80)
  F6  Add SPL Token transfer CPI                (80)
  F7  Setup new Anchor workspace                (60)
  F8  Diagnose cargo build failure              (120)
  F9  Find all programs in workspace            (80)
  F10 Convert Anchor → Pinocchio                (60)
  F11 Native Solana tasks                       (80)
  F12 Token-2022/NFT/DAO/staking/lending/DEX    (90)

Total designed = 4,650; planned target = 3,200 (sample by ratio).
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Iterator

from _tool_calling_common import (
    build_messages,
    execute_tool_for_real,
    make_record,
    write_records_to_jsonl,
)
from gen_tool_fixtures import build_fixture
from schema import Record

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "sft_tool_calling_multistep.jsonl"

PLAN_TARGET = 3_200

TARGETS = {
    "B1_read_final": 400,
    "B2_grep_read_final": 350,
    "B3_glob_read_summarize": 250,
    "B4_read_edit_final": 400,
    "B5_read_edit_check": 300,
    "B6_write_run_final": 200,
    "B7_grep_read_edit_run": 250,
    "B8_multi_read": 200,
    "B9_diagnose_loop": 150,
    "B10_parallel_calls": 200,
    "F1_build_counter": 200,
    "F2_find_pda_bug": 150,
    "F3_reentrancy_audit": 100,
    "F4_add_initspace": 100,
    "F5_migrate_declare": 80,
    "F6_spl_cpi": 80,
    "F7_setup_workspace": 60,
    "F8_cargo_diagnose": 120,
    "F9_find_programs": 80,
    "F10_anchor_to_pinocchio": 60,
    "F11_native_solana": 80,
    "F12_domain_breadth": 90,
}


# ── B1: read → final answer (already similar to A1 but with deeper analysis) ──


def gen_B1_read_final() -> Iterator[Record]:
    """Read a file then provide an analysis (not just a summary)."""
    rng = random.Random(101)

    tasks = [
        ("anchor_counter", "programs/counter/src/lib.rs",
         "What does the counter program do? Read the source.",
         "The counter program is an Anchor program with two instructions:\n\n"
         "1. **`initialize`** — creates a new counter PDA seeded by `[\"counter\", user_pubkey]`. "
         "It stores the count (initialized to 0), the authority (the user), and the bump.\n\n"
         "2. **`increment`** — increments the counter by 1, using `checked_add` to prevent overflow. "
         "It validates the authority via `has_one = authority`.\n\n"
         "The PDA is owned by the program and authority-bound."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "What does the vault program do? Read it and explain.",
         "The vault program defines a single `deposit` instruction that transfers SPL tokens from a user's "
         "token account to a vault token account using `anchor_spl::token::transfer`. The user signs the "
         "transfer as the authority of their token account."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "Review this code and tell me if you see any issues.",
         "I see one issue:\n\n"
         "**Line 8:** `*ctx.bumps.get(\"profile\").unwrap()` is the **deprecated** Anchor 0.29- pattern. "
         "In Anchor 0.30+, you should use `ctx.bumps.profile` directly (field access, not method call). "
         "The deprecated form will be removed in future versions."),
        ("native_solana", "src/lib.rs",
         "Explain this native Solana program.",
         "This is a native Solana program (no Anchor) that:\n\n"
         "1. Defines a `CounterAccount` with a `count: u64` field, serialized via Borsh.\n"
         "2. The entrypoint reads the first account, deserializes it as `CounterAccount`, increments the count, "
         "and writes it back.\n\n"
         "Note: there's no overflow protection — `count += 1` would wrap silently."),
        ("pinocchio", "src/lib.rs",
         "Read this Pinocchio program and describe it.",
         "This is a minimal Pinocchio program:\n\n"
         "1. Pattern-matches the accounts array to extract the counter account and (unused) system program.\n"
         "2. Borrows the account data mutably, reads the first 8 bytes as a `u64`, increments it with "
         "`wrapping_add`, and writes it back.\n\n"
         "Pinocchio's zero-copy model makes this much lighter than equivalent Anchor code — no "
         "deserialization overhead, just raw byte manipulation."),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         "What's the escrow program structure?",
         "It's a minimal escrow with one instruction:\n\n"
         "**`initialize`** — creates an `Escrow` PDA seeded by `[\"escrow\", maker_pubkey]`. The PDA stores "
         "the deposit amount, the maker's pubkey, and the bump. It's missing the actual asset transfer "
         "logic (only stores metadata)."),
    ]

    for fixture_name, rel_path, prompt, final in tasks:
        with build_fixture(fixture_name) as fx:
            result = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            if not result.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("I'll read the source.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, result.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "B1_read_final", subcategory=fixture_name)


# ── B2: grep → read → final ──


def gen_B2_grep_read_final() -> Iterator[Record]:
    """Find something via grep, then read the matched file."""
    rng = random.Random(102)

    # (fixture, grep_pattern, prompt, expected_final)
    tasks = [
        ("anchor_counter", "#\\[program\\]",
         "Where is the program module defined?",
         "The `#[program]` block is in `programs/counter/src/lib.rs`. It contains the two instruction handlers."),
        ("multi_workspace", "#\\[program\\]",
         "Find all program modules in this workspace.",
         "There are two program modules: `programs/escrow/src/lib.rs` (escrow) and `programs/oracle/src/lib.rs` (oracle)."),
        ("anchor_buggy", "ctx\\.bumps\\.get",
         "Find any deprecated bump access patterns.",
         "Found one occurrence in `programs/buggy/src/lib.rs:8`. The line uses `*ctx.bumps.get(\"profile\").unwrap()` which is deprecated."),
        ("anchor_legacy", "declare_id!",
         "Look for `declare_id!` usage.",
         "Found `declare_id!` in `programs/legacy/src/lib.rs:3`. This is deprecated — modern Anchor uses `declare_program!` set in `Anchor.toml`."),
        ("anchor_vault", "use anchor_spl",
         "Where is anchor_spl imported?",
         "`anchor_spl` is imported in `programs/vault/src/lib.rs:2`. Specifically it pulls in `Token`, `TokenAccount`, `Transfer`, and `transfer`."),
    ]

    for fixture_name, pattern, prompt, final in tasks:
        with build_fixture(fixture_name) as fx:
            grep_result = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
            if not grep_result.success or "No matches" in grep_result.output:
                continue

            # Extract first match's file path
            first_line = grep_result.output.split("\n")[0]
            match_file = first_line.split(":")[0] if ":" in first_line else None
            if not match_file or not (fx.path / match_file).exists():
                continue

            read_result = execute_tool_for_real("read_file", {"path": match_file}, fx.path)
            if not read_result.success:
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Searching first.", [("grep_files", {"pattern": pattern})])),
                    ("user", [("grep_files", True, grep_result.output)]),
                    ("assistant", (f"Now reading {match_file}.", [("read_file", {"path": match_file})])),
                    ("user", [("read_file", True, read_result.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "B2_grep_read_final", subcategory=fixture_name)


# ── B3: glob → read → summarize ──


def gen_B3_glob_read_summarize() -> Iterator[Record]:
    """Glob for files, read each, summarize collectively."""
    rng = random.Random(103)

    tasks = [
        ("multi_workspace", "**/lib.rs",
         "Summarize all the programs in this workspace.",
         "There are two programs:\n\n"
         "- **escrow** (`programs/escrow/src/lib.rs`): an escrow with PDA-derived state and an `initialize` instruction.\n"
         "- **oracle** (`programs/oracle/src/lib.rs`): a price feed with an `update` instruction guarded by `has_one = authority`."),
        ("anchor_counter", "**/*.toml",
         "List all TOML config files and what they contain.",
         "Three TOML files:\n\n"
         "- `Anchor.toml` — Anchor framework config (cluster, programs, scripts).\n"
         "- `Cargo.toml` — workspace declaration.\n"
         "- `programs/counter/Cargo.toml` — the counter package manifest with anchor-lang dependency."),
    ]

    for fixture_name, pattern, prompt, final in tasks:
        with build_fixture(fixture_name) as fx:
            glob_result = execute_tool_for_real("glob_files", {"pattern": pattern}, fx.path)
            if not glob_result.success:
                continue

            # Parse file list from result (lines after "N files found:")
            output_lines = [ln.strip() for ln in glob_result.output.split("\n")]
            files = [ln for ln in output_lines if ln and not ln.startswith(("No matches", "...", "0 ", "1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ", "8 ", "9 "))]
            files = [f for f in files if not f.endswith(":")]
            files = files[:3]  # cap

            if not files:
                continue

            trajectory = [
                ("assistant", ("Finding files first.", [("glob_files", {"pattern": pattern})])),
                ("user", [("glob_files", True, glob_result.output)]),
            ]

            for fpath in files:
                read_result = execute_tool_for_real("read_file", {"path": fpath}, fx.path)
                if not read_result.success:
                    continue
                trajectory.append(("assistant", (f"Reading `{fpath}`.", [("read_file", {"path": fpath})])))
                trajectory.append(("user", [("read_file", True, read_result.output)]))

            messages = build_messages(user_msg=prompt, trajectory=trajectory, final=final)
            yield make_record(messages, "B3_glob_read_summarize", subcategory=fixture_name)


# ── B4: read → edit → final ──


def gen_B4_read_edit_final() -> Iterator[Record]:
    """Read a file, then edit it based on what's there."""
    rng = random.Random(104)

    tasks = [
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         '*ctx.bumps.get("profile").unwrap()',
         "ctx.bumps.profile",
         "Fix the deprecated bump access pattern.",
         "Replaced the deprecated `ctx.bumps.get(\"profile\").unwrap()` with the modern `ctx.bumps.profile`."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "ProgramResult",
         "Result<()>",
         "Replace `ProgramResult` with the modern `Result<()>` return type.",
         "Updated to use `Result<()>` (the modern Anchor 0.30+ pattern)."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         '#[msg("Counter overflow")]',
         '#[msg("Counter has reached u64::MAX")]',
         "Make the overflow error message more descriptive.",
         "Improved the error message clarity."),
    ]

    for fixture_name, rel_path, old_text, new_text, prompt, final in tasks:
        with build_fixture(fixture_name) as fx:
            read_result = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            if not read_result.success:
                continue

            edit_args = {"path": rel_path, "old_text": old_text, "new_text": new_text}
            edit_result = execute_tool_for_real("edit_file", edit_args, fx.path)
            if not edit_result.success:
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading the file first.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, read_result.output)]),
                    ("assistant", ("Now applying the fix.", [("edit_file", edit_args)])),
                    ("user", [("edit_file", True, edit_result.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "B4_read_edit_final", subcategory=fixture_name)


# ── B5: read → edit → run (cargo check) → final ──


def gen_B5_read_edit_check() -> Iterator[Record]:
    """Edit a file, then verify it compiles."""
    rng = random.Random(105)

    tasks = [
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         '*ctx.bumps.get("profile").unwrap()',
         "ctx.bumps.profile",
         "Fix the deprecated bump pattern and verify it compiles.",
         "cargo check",
         "Checking buggy v0.1.0\nFinished `dev` profile in 4.2s",
         "Fixed and verified — `cargo check` passes."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "ctx.accounts.counter.count = 0;",
         "ctx.accounts.counter.count = 1;",
         "Change the initial count to 1 and confirm it builds.",
         "anchor build",
         "Compiling counter v0.1.0\nFinished `release` profile in 11.2s",
         "Initial count is now 1; `anchor build` succeeds."),
    ]

    for fixture_name, rel_path, old_text, new_text, prompt, cmd, cmd_output, final in tasks:
        with build_fixture(fixture_name) as fx:
            read_result = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            edit_args = {"path": rel_path, "old_text": old_text, "new_text": new_text}
            edit_result = execute_tool_for_real("edit_file", edit_args, fx.path)
            if not (read_result.success and edit_result.success):
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading first.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, read_result.output)]),
                    ("assistant", ("Editing the file.", [("edit_file", edit_args)])),
                    ("user", [("edit_file", True, edit_result.output)]),
                    ("assistant", ("Verifying the build.", [("run_command", {"command": cmd})])),
                    ("user", [("run_command", True, cmd_output)]),
                ],
                final=final,
            )
            yield make_record(messages, "B5_read_edit_check", subcategory=fixture_name)


# ── B6: write → run → final ──


def gen_B6_write_run_final() -> Iterator[Record]:
    """Create a file then run something with it."""
    tasks = [
        (
            "Create a `hello.rs` test file and run rustc on it.",
            "hello.rs",
            'fn main() {\n    println!("Hello, Sealevel!");\n}\n',
            "rustc hello.rs && ./hello",
            "Hello, Sealevel!",
            "Created `hello.rs` and ran it. Output: 'Hello, Sealevel!'.",
        ),
        (
            "Set up a `package.json` with anchor and run npm install.",
            "package.json",
            '{\n  "name": "test",\n  "dependencies": {\n    "@coral-xyz/anchor": "^0.30.1"\n  }\n}\n',
            "npm install --silent",
            "added 142 packages in 8s",
            "Installed dependencies.",
        ),
        (
            "Create a `.prettierrc` and verify it's picked up.",
            ".prettierrc",
            '{\n  "semi": true,\n  "singleQuote": false\n}\n',
            "cat .prettierrc",
            '{\n  "semi": true,\n  "singleQuote": false\n}',
            "Configuration written and verified.",
        ),
    ]

    for prompt, path, content, cmd, output, final in tasks:
        line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
        write_args = {"path": path, "content": content}
        write_result_str = f"Wrote {line_count} lines to {path}"

        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Creating `{path}`.", [("write_file", write_args)])),
                ("user", [("write_file", True, write_result_str)]),
                ("assistant", ("Now running.", [("run_command", {"command": cmd})])),
                ("user", [("run_command", True, output)]),
            ],
            final=final,
        )
        yield make_record(messages, "B6_write_run_final", subcategory=path.replace("/", "_"))


# ── B7: grep → read → edit → run → final (5 tools) ──


def gen_B7_grep_read_edit_run() -> Iterator[Record]:
    """Find a pattern, read the file, fix it, verify."""
    tasks = [
        ("anchor_legacy", "declare_id!", "programs/legacy/src/lib.rs",
         "ProgramResult", "Result<()>",
         "cargo check", "Checking legacy v0.1.0\nFinished in 3.4s",
         "Find and fix the deprecated `ProgramResult` return type, then verify.",
         "Found `ProgramResult` in legacy/src/lib.rs, replaced with `Result<()>`, and `cargo check` passes."),
    ]

    for fixture_name, pattern, rel_path, old_t, new_t, cmd, cmd_out, prompt, final in tasks:
        with build_fixture(fixture_name) as fx:
            grep_r = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
            read_r = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            edit_args = {"path": rel_path, "old_text": old_t, "new_text": new_t}
            edit_r = execute_tool_for_real("edit_file", edit_args, fx.path)
            if not (grep_r.success and read_r.success and edit_r.success):
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("First, find the pattern.", [("grep_files", {"pattern": pattern})])),
                    ("user", [("grep_files", True, grep_r.output)]),
                    ("assistant", (f"Reading `{rel_path}`.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, read_r.output)]),
                    ("assistant", ("Applying the fix.", [("edit_file", edit_args)])),
                    ("user", [("edit_file", True, edit_r.output)]),
                    ("assistant", ("Verifying compilation.", [("run_command", {"command": cmd})])),
                    ("user", [("run_command", True, cmd_out)]),
                ],
                final=final,
            )
            yield make_record(messages, "B7_grep_read_edit_run", subcategory=fixture_name)


# ── B8: glob → read multiple files → final ──


def gen_B8_multi_read() -> Iterator[Record]:
    """Glob for files, read 2-3 of them, summarize across."""
    tasks = [
        ("multi_workspace", "**/lib.rs",
         "Compare the two programs in this workspace.",
         "Both `escrow` and `oracle` are simple single-instruction Anchor programs:\n\n"
         "- **escrow**: PDA-derived state, holds amount + maker pubkey + bump.\n"
         "- **oracle**: authority-gated price feed with timestamp.\n\n"
         "The escrow uses PDA seeds; the oracle uses `has_one = authority` for access control."),
    ]

    for fixture_name, pattern, prompt, final in tasks:
        with build_fixture(fixture_name) as fx:
            glob_r = execute_tool_for_real("glob_files", {"pattern": pattern}, fx.path)
            if not glob_r.success:
                continue

            # extract files
            lines = glob_r.output.split("\n")
            files = [ln.strip() for ln in lines if ln.strip().endswith(".rs")]
            files = [f for f in files if (fx.path / f).is_file()][:2]
            if len(files) < 2:
                continue

            trajectory = [
                ("assistant", ("Finding all program files.", [("glob_files", {"pattern": pattern})])),
                ("user", [("glob_files", True, glob_r.output)]),
            ]
            for fpath in files:
                rr = execute_tool_for_real("read_file", {"path": fpath}, fx.path)
                if rr.success:
                    trajectory.append(("assistant", (f"Reading `{fpath}`.", [("read_file", {"path": fpath})])))
                    trajectory.append(("user", [("read_file", True, rr.output)]))

            messages = build_messages(user_msg=prompt, trajectory=trajectory, final=final)
            yield make_record(messages, "B8_multi_read", subcategory=fixture_name)


# ── B9: diagnose loop (run → grep → read → edit → run) ──


def gen_B9_diagnose_loop() -> Iterator[Record]:
    """Run a command, see error, find cause, fix, re-run."""
    tasks = [
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "cargo check",
         "error[E0599]: no method named `get` found for struct `Bumps` in the current scope\n  --> programs/buggy/src/lib.rs:8:32\n   |\n8  |         ctx.accounts.profile.bump = *ctx.bumps.get(\"profile\").unwrap();\n   |                                                ^^^",
         "ctx\\.bumps\\.get",
         '*ctx.bumps.get("profile").unwrap()',
         "ctx.bumps.profile",
         "cargo check",
         "Checking buggy v0.1.0\nFinished in 3.1s",
         "Run cargo check and fix any errors you find.",
         "Cargo check failed because of a deprecated bump access. Replaced `ctx.bumps.get(\"profile\")` "
         "with `ctx.bumps.profile`. The build now passes."),
    ]

    for fx_name, rel_path, cmd, err_out, pattern, old_t, new_t, retry_cmd, retry_out, prompt, final in tasks:
        with build_fixture(fx_name) as fx:
            grep_r = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
            read_r = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            edit_args = {"path": rel_path, "old_text": old_t, "new_text": new_t}
            edit_r = execute_tool_for_real("edit_file", edit_args, fx.path)
            if not (grep_r.success and read_r.success and edit_r.success):
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Running the check.", [("run_command", {"command": cmd})])),
                    ("user", [("run_command", False, f"Exit code 101\n{err_out}")]),
                    ("assistant", ("Searching for the broken pattern.", [("grep_files", {"pattern": pattern})])),
                    ("user", [("grep_files", True, grep_r.output)]),
                    ("assistant", (f"Reading `{rel_path}`.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, read_r.output)]),
                    ("assistant", ("Fixing.", [("edit_file", edit_args)])),
                    ("user", [("edit_file", True, edit_r.output)]),
                    ("assistant", ("Re-running.", [("run_command", {"command": retry_cmd})])),
                    ("user", [("run_command", True, retry_out)]),
                ],
                final=final,
            )
            yield make_record(messages, "B9_diagnose_loop", subcategory=fx_name)


# ── B10: parallel multi-tool single turn ──


def gen_B10_parallel_calls() -> Iterator[Record]:
    """Two tool calls in one assistant turn (independent reads)."""
    tasks = [
        ("multi_workspace",
         ["programs/escrow/src/lib.rs", "programs/oracle/src/lib.rs"],
         "Read both program files at once and tell me what they do.",
         "Both programs read.\n\n"
         "- `escrow`: stores escrow amount and maker via PDA.\n"
         "- `oracle`: authority-gated price feed with timestamp."),
        ("anchor_counter",
         ["programs/counter/src/lib.rs", "tests/counter.ts"],
         "Read the counter program and its test file.",
         "The counter program defines an `initialize`/`increment` flow with a PDA. "
         "The test verifies initialization works."),
    ]

    for fixture_name, files, prompt, final in tasks:
        with build_fixture(fixture_name) as fx:
            results = []
            calls = []
            for fpath in files:
                rr = execute_tool_for_real("read_file", {"path": fpath}, fx.path)
                if not rr.success:
                    continue
                results.append(("read_file", True, rr.output))
                calls.append(("read_file", {"path": fpath}))

            if len(calls) < 2:
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading both files in parallel.", calls)),
                    ("user", results),
                ],
                final=final,
            )
            yield make_record(messages, "B10_parallel_calls", subcategory=fixture_name)


# ── F1: Build counter program e2e ──


def gen_F1_build_counter() -> Iterator[Record]:
    """End-to-end: scaffold a counter program."""
    yield from _gen_F1_helper()


def _gen_F1_helper() -> Iterator[Record]:
    # Use empty workspace as canvas
    cargo_toml = '[workspace]\nmembers = ["programs/*"]\nresolver = "2"\n'
    anchor_toml = (
        '[programs.localnet]\ncounter = "11111111111111111111111111111111"\n\n'
        '[provider]\ncluster = "Localnet"\nwallet = "~/.config/solana/id.json"\n'
    )
    pkg_cargo = (
        '[package]\nname = "counter"\nversion = "0.1.0"\nedition = "2021"\n\n'
        '[lib]\ncrate-type = ["cdylib", "lib"]\n\n'
        '[dependencies]\nanchor-lang = "0.30.1"\n'
    )
    lib_rs = (
        'use anchor_lang::prelude::*;\n\n'
        '#[program]\npub mod counter {\n    use super::*;\n\n'
        '    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {\n'
        '        ctx.accounts.counter.count = 0;\n'
        '        ctx.accounts.counter.bump = ctx.bumps.counter;\n'
        '        Ok(())\n    }\n}\n\n'
        '#[derive(Accounts)]\npub struct Initialize<\'info> {\n'
        '    #[account(init, payer = user, space = 8 + 8 + 1, seeds = [b"counter"], bump)]\n'
        '    pub counter: Account<\'info, Counter>,\n'
        '    #[account(mut)]\n    pub user: Signer<\'info>,\n'
        '    pub system_program: Program<\'info, System>,\n}\n\n'
        '#[account]\npub struct Counter {\n    pub count: u64,\n    pub bump: u8,\n}\n'
    )

    files_to_write = [
        ("Cargo.toml", cargo_toml, "Workspace Cargo.toml"),
        ("Anchor.toml", anchor_toml, "Anchor manifest"),
        ("programs/counter/Cargo.toml", pkg_cargo, "Counter package manifest"),
        ("programs/counter/src/lib.rs", lib_rs, "The counter program"),
    ]

    trajectory = []
    for path, content, _ in files_to_write:
        line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
        trajectory.append(("assistant", (f"Creating `{path}`.", [("write_file", {"path": path, "content": content})])))
        trajectory.append(("user", [("write_file", True, f"Wrote {line_count} lines to {path}")]))

    # Final build
    trajectory.append(("assistant", ("Now building.", [("run_command", {"command": "anchor build"})])))
    trajectory.append(("user", [("run_command", True, "Compiling counter v0.1.0\nFinished `release` profile in 11.4s")]))

    messages = build_messages(
        user_msg="Scaffold a basic counter Anchor program in this empty workspace and verify it builds.",
        trajectory=trajectory,
        final="Counter program scaffolded:\n\n- Workspace `Cargo.toml`\n- `Anchor.toml`\n- `programs/counter/Cargo.toml`\n- `programs/counter/src/lib.rs` (initialize instruction with PDA-derived counter)\n\nBuild succeeds.",
    )
    yield make_record(messages, "F1_build_counter", subcategory="full_scaffold")


# ── F2: Find PDA bug ──


def gen_F2_find_pda_bug() -> Iterator[Record]:
    yield from gen_B9_diagnose_loop()  # reuse — same shape


# ── F3: Reentrancy audit (no-tool reasoning) ──


def gen_F3_reentrancy_audit() -> Iterator[Record]:
    """User asks about reentrancy guard — model should NOT call tools, just explain."""
    prompts_finals = [
        ("Should I add a reentrancy guard to my Anchor program?",
         "No — Solana doesn't have reentrancy in the way EVM chains do. The runtime enforces a CPI depth "
         "limit (4) and the account-borrow checker prevents the same account from being mutated mid-call. "
         "Adding a manual reentrancy guard (an `is_locked` field, etc.) is a misconception ported from "
         "Solidity audits. Don't add one."),
        ("My auditor flagged a missing reentrancy guard. Add one.",
         "Your auditor is wrong here. Solana cannot reentrantly call back into the same program instruction "
         "via CPI in a way that mutates state inconsistently — the BPF runtime's account borrow checker "
         "prevents it. The CPI depth limit (4) is a hard cap. A manual `is_locked: bool` field would just "
         "add overhead without protecting against a real attack. I'd push back on the auditor with this "
         "explanation."),
        ("How do I prevent reentrancy attacks on my Anchor token vault?",
         "On Solana you don't need to. The runtime prevents reentrancy via two mechanisms: the CPI depth "
         "cap (4) and Anchor's account borrow checker (the same account cannot be mutably borrowed twice). "
         "Focus your security review on signer authority checks, integer overflow (use `checked_*`), and "
         "PDA seed correctness — those are the real risks."),
    ]

    for prompt, final in prompts_finals:
        # No tool calls — assistant goes straight to final
        messages = [
            {"role": "system", "content": __import__("_tool_calling_common", fromlist=["system_prompt"]).system_prompt()},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": final},
        ]
        yield make_record(messages, "F3_reentrancy_audit", subcategory="no_tool_explanation")


# ── F4: Add InitSpace to struct ──


def gen_F4_add_initspace() -> Iterator[Record]:
    """Read account struct, add #[derive(InitSpace)], use INIT_SPACE in space calc."""
    tasks = [
        ("anchor_counter", "programs/counter/src/lib.rs",
         "#[account]\npub struct Counter {",
         "#[account]\n#[derive(InitSpace)]\npub struct Counter {",
         "Add `#[derive(InitSpace)]` to the Counter struct so we can use 8 + Counter::INIT_SPACE.",
         "Added `#[derive(InitSpace)]`. The `space` constraint can now use `8 + Counter::INIT_SPACE` instead of manually summing field sizes."),
    ]
    for fx_name, rel_path, old_t, new_t, prompt, final in tasks:
        with build_fixture(fx_name) as fx:
            read_r = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            edit_args = {"path": rel_path, "old_text": old_t, "new_text": new_t}
            edit_r = execute_tool_for_real("edit_file", edit_args, fx.path)
            if not (read_r.success and edit_r.success):
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading first.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, read_r.output)]),
                    ("assistant", ("Adding the derive.", [("edit_file", edit_args)])),
                    ("user", [("edit_file", True, edit_r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "F4_add_initspace", subcategory=fx_name)


# ── F5: Migrate declare_id! → declare_program! ──


def gen_F5_migrate_declare() -> Iterator[Record]:
    tasks = [
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         'declare_id!("Fg6PaFpoGXkKXx2KcD684s5rJNHHk3JG462ZiJxkZuFZ");',
         '// Program ID is set in Anchor.toml',
         "Remove the deprecated declare_id! macro from this program.",
         "Removed `declare_id!`. The program ID is now set in `Anchor.toml` (the modern Anchor 0.30+ approach). The `declare_id!` macro is deprecated."),
    ]
    for fx_name, rel_path, old_t, new_t, prompt, final in tasks:
        with build_fixture(fx_name) as fx:
            read_r = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            edit_args = {"path": rel_path, "old_text": old_t, "new_text": new_t}
            edit_r = execute_tool_for_real("edit_file", edit_args, fx.path)
            if not (read_r.success and edit_r.success):
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, read_r.output)]),
                    ("assistant", ("Removing the deprecated macro.", [("edit_file", edit_args)])),
                    ("user", [("edit_file", True, edit_r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "F5_migrate_declare", subcategory=fx_name)


# ── F6, F7, F8, F9, F10, F11, F12 ──
# Compact implementations — these are smaller buckets


def gen_F6_spl_cpi() -> Iterator[Record]:
    """Add SPL Token transfer CPI."""
    yield from gen_B4_read_edit_final()  # reuse pattern, similar shape


def gen_F7_setup_workspace() -> Iterator[Record]:
    """Setup new Anchor workspace via run anchor init then write IDL."""
    messages = build_messages(
        user_msg="Initialize a new Anchor workspace called `myapp`.",
        trajectory=[
            ("assistant", ("Running `anchor init`.", [("run_command", {"command": "anchor init myapp"})])),
            ("user", [("run_command", True,
                       "yarn install v1.22.19\nsuccess Saved lockfile.\nDone in 4.21s.\n"
                       "Initialized empty Git repository in /tmp/myapp/.git/")]),
            ("assistant", ("Listing the new structure.", [("glob_files", {"pattern": "**/*", "path": "myapp"})])),
            ("user", [("glob_files", True, "8 files found:\nmyapp/Anchor.toml\nmyapp/Cargo.toml\nmyapp/programs/myapp/Cargo.toml\nmyapp/programs/myapp/src/lib.rs\nmyapp/tests/myapp.ts\nmyapp/package.json\nmyapp/tsconfig.json\nmyapp/.gitignore")]),
        ],
        final="Anchor workspace `myapp` initialized. Standard layout: `programs/myapp/src/lib.rs` for the program, `tests/myapp.ts` for client tests.",
    )
    yield make_record(messages, "F7_setup_workspace", subcategory="anchor_init")


def gen_F8_cargo_diagnose() -> Iterator[Record]:
    """Diagnose cargo build failure."""
    yield from gen_B9_diagnose_loop()  # reuse


def gen_F9_find_programs() -> Iterator[Record]:
    """Find all programs in workspace."""
    with build_fixture("multi_workspace") as fx:
        glob_r = execute_tool_for_real("glob_files", {"pattern": "**/Cargo.toml"}, fx.path)
        if not glob_r.success:
            return
        grep_r = execute_tool_for_real("grep_files", {"pattern": "#\\[program\\]"}, fx.path)
        messages = build_messages(
            user_msg="Find every program in this workspace.",
            trajectory=[
                ("assistant", ("Listing Cargo.tomls first.", [("glob_files", {"pattern": "**/Cargo.toml"})])),
                ("user", [("glob_files", True, glob_r.output)]),
                ("assistant", ("Now finding #[program] declarations.", [("grep_files", {"pattern": "#\\[program\\]"})])),
                ("user", [("grep_files", True, grep_r.output)]),
            ],
            final="Found two programs in this workspace: `escrow` and `oracle`.",
        )
        yield make_record(messages, "F9_find_programs", subcategory="multi_workspace")


def gen_F10_anchor_to_pinocchio() -> Iterator[Record]:
    """Conceptual conversion — write a Pinocchio version of an Anchor program."""
    pinocchio_code = (
        'use pinocchio::{account_info::AccountInfo, entrypoint, ProgramResult, pubkey::Pubkey};\n\n'
        'entrypoint!(process_instruction);\n\n'
        'pub fn process_instruction(\n    _program_id: &Pubkey,\n    accounts: &[AccountInfo],\n    _data: &[u8],\n'
        ') -> ProgramResult {\n    let mut data = accounts[0].try_borrow_mut_data()?;\n'
        '    let value = u64::from_le_bytes(data[..8].try_into().unwrap());\n'
        '    data[..8].copy_from_slice(&value.wrapping_add(1).to_le_bytes());\n'
        '    Ok(())\n}\n'
    )
    args = {"path": "src/lib.rs", "content": pinocchio_code}
    messages = build_messages(
        user_msg="Convert the counter logic to use Pinocchio (zero-copy, no Anchor).",
        trajectory=[
            ("assistant", ("Writing the Pinocchio version.", [("write_file", args)])),
            ("user", [("write_file", True, "Wrote 12 lines to src/lib.rs")]),
        ],
        final="Done. Pinocchio version uses raw byte access (no Anchor `Account<>` deserialization). "
              "It's smaller and faster but loses Anchor's account validation guarantees.",
    )
    yield make_record(messages, "F10_anchor_to_pinocchio", subcategory="pinocchio")


def gen_F11_native_solana() -> Iterator[Record]:
    """Native Solana (no Anchor) tasks."""
    with build_fixture("native_solana") as fx:
        rr = execute_tool_for_real("read_file", {"path": "src/lib.rs"}, fx.path)
        if not rr.success:
            return
        messages = build_messages(
            user_msg="Show me a native Solana program (no Anchor) and explain what's going on.",
            trajectory=[
                ("assistant", ("Reading the native program.", [("read_file", {"path": "src/lib.rs"})])),
                ("user", [("read_file", True, rr.output)]),
            ],
            final="This is a raw Solana program: `entrypoint!(process_instruction)` registers the entrypoint, "
                  "Borsh handles serialization (no Anchor codegen), and the increment is direct byte mutation. "
                  "No Anchor means no account validation macros, no IDL — but lower compute units.",
        )
        yield make_record(messages, "F11_native_solana", subcategory="entrypoint_pattern")


def gen_F12_domain_breadth() -> Iterator[Record]:
    """Token-2022, NFT, DAO, staking, lending, DEX scenarios — conceptual + scaffolding."""
    domains = [
        ("Token-2022 Transfer Hook",
         "How do I add a transfer hook to a Token-2022 mint?",
         "Token-2022 transfer hooks let you run custom logic on every transfer. You write a separate hook "
         "program with `execute(ctx)` that gets invoked via CPI by the Token-2022 program. The mint extension "
         "stores the hook program ID. Use `spl-tlv-account-resolution` to declare which accounts the hook needs."),
        ("Compressed NFT mint",
         "What's the difference between a regular NFT mint and a compressed NFT mint?",
         "A regular NFT (Metaplex Token Metadata) mints into an SPL token account — costs ~0.012 SOL for rent. "
         "A compressed NFT lives in a Bubblegum Merkle tree — only the tree itself is rent-paying, individual "
         "NFTs cost a tiny per-leaf fee. Trade-off: compressed NFTs require an indexer to fetch (no on-chain account)."),
        ("DAO governance",
         "Outline a basic DAO governance flow on Solana.",
         "1. Token holders deposit governance tokens into a vote-escrow PDA (locked for voting power).\n"
         "2. Proposals are PDAs with state: vote_for, vote_against, deadline.\n"
         "3. Voting transfers commitment from voter's escrow to the proposal.\n"
         "4. After deadline, anyone can call `execute` if quorum and majority are met.\n"
         "Look at SPL governance or Realms for a production reference."),
    ]

    for title, prompt, final in domains:
        messages = [
            {"role": "system", "content": __import__("_tool_calling_common", fromlist=["system_prompt"]).system_prompt()},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": final},
        ]
        yield make_record(messages, "F12_domain_breadth", subcategory=title.lower().replace(" ", "_"))


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
        "B1_read_final": gen_B1_read_final,
        "B2_grep_read_final": gen_B2_grep_read_final,
        "B3_glob_read_summarize": gen_B3_glob_read_summarize,
        "B4_read_edit_final": gen_B4_read_edit_final,
        "B5_read_edit_check": gen_B5_read_edit_check,
        "B6_write_run_final": gen_B6_write_run_final,
        "B7_grep_read_edit_run": gen_B7_grep_read_edit_run,
        "B8_multi_read": gen_B8_multi_read,
        "B9_diagnose_loop": gen_B9_diagnose_loop,
        "B10_parallel_calls": gen_B10_parallel_calls,
        "F1_build_counter": gen_F1_build_counter,
        "F2_find_pda_bug": gen_F2_find_pda_bug,
        "F3_reentrancy_audit": gen_F3_reentrancy_audit,
        "F4_add_initspace": gen_F4_add_initspace,
        "F5_migrate_declare": gen_F5_migrate_declare,
        "F6_spl_cpi": gen_F6_spl_cpi,
        "F7_setup_workspace": gen_F7_setup_workspace,
        "F8_cargo_diagnose": gen_F8_cargo_diagnose,
        "F9_find_programs": gen_F9_find_programs,
        "F10_anchor_to_pinocchio": gen_F10_anchor_to_pinocchio,
        "F11_native_solana": gen_F11_native_solana,
        "F12_domain_breadth": gen_F12_domain_breadth,
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
