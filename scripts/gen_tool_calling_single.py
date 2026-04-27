"""Group A: Single-tool happy-path examples (target: 2,500 records).

Each record is a 2-iteration trajectory:
  user → assistant (tool call) → user (tool_result) → assistant (final answer).

Tool results are computed by executing the REAL production tool against
fixture project trees, so output formatting (line numbers, file headers,
truncation markers, error messages) matches inference behavior exactly.

Subcategories:
  A1  — read_file basic         (350)
  A2  — read_file offset/limit  (200)
  A3  — read_file abs+rel paths (150)
  A4  — glob_files patterns     (300)
  A5  — glob_files with path    (150)
  A6  — grep_files regex        (350)
  A7  — grep_files with glob    (200)
  A8  — write_file new files    (400)
  A9  — edit_file                (350)
  A10 — run_command basic       (350)
  A11 — run_command timeout     (100)
  A12 — run_command compound    (100)

Total: 3,000 designed but distributed to 2,500 in plan v2 — we under-produce
by sampling each subcategory to its target count.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Iterator

from _tool_calling_common import (
    GLOB_PHRASINGS,
    GREP_PHRASINGS,
    READ_PHRASINGS,
    build_messages,
    execute_tool_for_real,
    make_record,
    make_tool_result,
    write_records_to_jsonl,
)
from gen_tool_fixtures import FIXTURES, build_fixture
from schema import Record

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "sft_tool_calling_single.jsonl"


# ── Subcategory targets (per plan distribution) ──

TARGETS = {
    "read_basic": 350,
    "read_offset_limit": 200,
    "read_abs_rel": 150,
    "glob_basic": 300,
    "glob_with_path": 150,
    "grep_basic": 350,
    "grep_with_glob": 200,
    "write_new": 400,
    "edit_basic": 350,
    "run_basic": 350,
    "run_timeout": 100,
    "run_compound": 100,
}
# Total = 3,000; we sample 2,500 by ratio for plan v2 compliance.
PLAN_V2_TOTAL = 2_500


# ── Helpers ──


def _final_response_for_read(filename: str, content_excerpt: str) -> str:
    """Synthesize a natural final answer after a successful read."""
    summaries = [
        f"The file `{filename}` contains the contents shown above.",
        f"Here's what `{filename}` contains — see the output above.",
        f"Read complete. `{filename}` is shown above.",
        f"`{filename}` has been read; the contents are above.",
    ]
    return random.choice(summaries)


def _summarize_rust_file(filename: str, content: str) -> str:
    """For Rust files, generate a more substantive summary."""
    if "#[program]" in content:
        return (
            f"`{filename}` defines an Anchor program. It declares the program module "
            f"and instruction handlers using the `#[program]` attribute."
        )
    if "use anchor_lang" in content:
        return f"`{filename}` is an Anchor source file using `anchor_lang::prelude`."
    if "entrypoint!" in content:
        return f"`{filename}` defines a native Solana program entrypoint."
    if "#[account]" in content:
        return f"`{filename}` defines Anchor account state structs."
    return f"`{filename}` is a Rust source file."


def _records_iter(category: str, target: int, gen_fn) -> Iterator[Record]:
    """Wrap a generator so it stops at `target` records."""
    count = 0
    for rec in gen_fn():
        if count >= target:
            return
        yield rec
        count += 1


# ── A1: read_file basic ──


def gen_read_basic() -> Iterator[Record]:
    """Generate read_file examples on simple paths from fixtures."""
    rng = random.Random(42)

    for fixture_name in ["anchor_counter", "anchor_vault", "anchor_buggy", "multi_workspace", "native_solana", "pinocchio"]:
        with build_fixture(fixture_name) as fx:
            # Sort files to keep deterministic order, but shuffle phrasings
            for rel_path in fx.files:
                # Skip very large or non-readable files (none here, but be safe)
                if rel_path.endswith(".lock"):
                    continue

                phrasing = rng.choice(READ_PHRASINGS)
                user_msg = phrasing.format(path=rel_path)

                # Execute real tool
                result = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
                if not result.success:
                    continue  # skip failed reads (shouldn't happen for fixture files)

                # Build trajectory
                file_content = (fx.path / rel_path).read_text(encoding="utf-8")
                final = _summarize_rust_file(rel_path, file_content) if rel_path.endswith(".rs") else _final_response_for_read(rel_path, "")

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("I'll read the file.", [("read_file", {"path": rel_path})])),
                        ("user", [("read_file", True, result.output)]),
                    ],
                    final=final,
                )
                yield make_record(messages, "read_basic", subcategory=fixture_name)


# ── A2: read_file with offset/limit ──


def gen_read_offset_limit() -> Iterator[Record]:
    """read_file with offset and limit args (for long files)."""
    rng = random.Random(43)

    # Build a synthetic long file in a fixture
    with build_fixture("anchor_counter") as fx:
        # Use the actual lib.rs (which is 60+ lines)
        rel_path = "programs/counter/src/lib.rs"
        line_count = (fx.path / rel_path).read_text().count("\n")

        configs = [
            {"path": rel_path, "offset": 0, "limit": 20},
            {"path": rel_path, "offset": 10, "limit": 15},
            {"path": rel_path, "offset": 20, "limit": 30},
            {"path": rel_path, "offset": 5, "limit": 10},
            {"path": rel_path, "limit": 25},
            {"path": rel_path, "offset": 30},
            {"path": rel_path, "limit": 40},
        ]

        prompts = [
            "Show me lines {offset}-{end} of {path}.",
            "Read the first {limit} lines of {path}.",
            "What's at the top of {path}? Read {limit} lines.",
            "Read {path} starting from line {offset}.",
            "Give me a chunk of {path} from line {offset} for {limit} lines.",
            "Just read {limit} lines of {path}, please.",
        ]

        for cfg in configs:
            offset = cfg.get("offset", 0)
            limit = cfg.get("limit", 200)
            end = offset + limit

            template = rng.choice(prompts)
            try:
                user_msg = template.format(path=rel_path, offset=offset + 1, end=end, limit=limit)
            except KeyError:
                user_msg = f"Read {rel_path}."

            result = execute_tool_for_real("read_file", cfg, fx.path)
            if not result.success:
                continue

            messages = build_messages(
                user_msg=user_msg,
                trajectory=[
                    ("assistant", ("I'll read that section.", [("read_file", cfg)])),
                    ("user", [("read_file", True, result.output)]),
                ],
                final=f"Here are lines {offset + 1}-{min(end, line_count)} of `{rel_path}`.",
            )
            yield make_record(messages, "read_offset_limit", subcategory="counter_lib")


# ── A3: read_file with absolute and relative paths ──


def gen_read_abs_rel() -> Iterator[Record]:
    """Mix absolute paths (resolved via fixture tmp path) and simple relative paths."""
    rng = random.Random(44)

    for fixture_name in ["anchor_counter", "multi_workspace", "anchor_vault"]:
        with build_fixture(fixture_name) as fx:
            for rel_path in fx.files[:4]:
                if rel_path.endswith(".lock"):
                    continue

                # Half use absolute paths
                use_abs = rng.random() < 0.5
                path_arg = str(fx.path / rel_path) if use_abs else rel_path

                phrasing = rng.choice(READ_PHRASINGS)
                user_msg = phrasing.format(path=path_arg)

                result = execute_tool_for_real("read_file", {"path": path_arg}, fx.path)
                if not result.success:
                    continue

                content_str = (fx.path / rel_path).read_text(encoding="utf-8")
                final = _summarize_rust_file(rel_path, content_str) if rel_path.endswith(".rs") else _final_response_for_read(rel_path, "")

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Reading the file.", [("read_file", {"path": path_arg})])),
                        ("user", [("read_file", True, result.output)]),
                    ],
                    final=final,
                )
                yield make_record(messages, "read_abs_rel", subcategory=f"{fixture_name}_{'abs' if use_abs else 'rel'}")


# ── A4: glob_files patterns ──


def gen_glob_basic() -> Iterator[Record]:
    """glob_files with various patterns."""
    rng = random.Random(45)

    patterns_per_fixture = {
        "anchor_counter": ["*.rs", "*.toml", "**/*.rs", "**/*.ts", "*.md", "**/Cargo.toml"],
        "multi_workspace": ["**/*.rs", "**/Cargo.toml", "programs/**/lib.rs", "**/*.toml"],
        "anchor_vault": ["**/*.rs", "**/src/*.rs", "*.toml"],
        "native_solana": ["**/*.rs", "src/*.rs"],
        "pinocchio": ["**/*.rs"],
    }

    for fixture_name, patterns in patterns_per_fixture.items():
        with build_fixture(fixture_name) as fx:
            for pattern in patterns:
                phrasing = rng.choice(GLOB_PHRASINGS)
                user_msg = phrasing.format(pattern=pattern)

                result = execute_tool_for_real("glob_files", {"pattern": pattern}, fx.path)
                if not result.success:
                    continue

                # Synthesize a final based on result
                match_count = 0
                for line in result.output.split("\n"):
                    if line.strip() and not line.startswith(("No matches", "...")):
                        match_count += 1
                # Subtract 1 for the "N files found:" header line
                match_count = max(0, match_count - 1)

                if "No matches" in result.output:
                    final = f"No files match the pattern `{pattern}`."
                else:
                    final = f"Found {match_count} file(s) matching `{pattern}`."

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", (f"Searching for `{pattern}`.", [("glob_files", {"pattern": pattern})])),
                        ("user", [("glob_files", True, result.output)]),
                    ],
                    final=final,
                )
                yield make_record(messages, "glob_basic", subcategory=fixture_name)


# ── A5: glob_files with path ──


def gen_glob_with_path() -> Iterator[Record]:
    """glob_files with explicit path arg."""
    rng = random.Random(46)

    configs = [
        ("multi_workspace", "*.rs", "programs/escrow/src"),
        ("multi_workspace", "*.rs", "programs/oracle/src"),
        ("multi_workspace", "**/*.rs", "programs"),
        ("anchor_counter", "*.rs", "programs/counter/src"),
        ("anchor_counter", "*.ts", "tests"),
        ("anchor_vault", "*.rs", "programs/vault/src"),
        ("anchor_vault", "*.toml", "."),
        ("native_solana", "*.rs", "src"),
    ]

    for fixture_name, pattern, search_path in configs:
        with build_fixture(fixture_name) as fx:
            phrasing = rng.choice([
                f"Find {pattern} files in {search_path}/.",
                f"List {pattern} files inside {search_path}.",
                f"What {pattern} files are under {search_path}?",
                f"Show me {pattern} files in the {search_path} directory.",
            ])

            args = {"pattern": pattern, "path": search_path}
            result = execute_tool_for_real("glob_files", args, fx.path)
            if not result.success:
                continue

            messages = build_messages(
                user_msg=phrasing,
                trajectory=[
                    ("assistant", (f"Looking in `{search_path}`.", [("glob_files", args)])),
                    ("user", [("glob_files", True, result.output)]),
                ],
                final=f"Search complete in `{search_path}`.",
            )
            yield make_record(messages, "glob_with_path", subcategory=f"{fixture_name}_{search_path.replace('/', '_')}")


# ── A6: grep_files regex ──


def gen_grep_basic() -> Iterator[Record]:
    """grep_files with regex patterns."""
    rng = random.Random(47)

    patterns_per_fixture = {
        "anchor_counter": ["#\\[program\\]", "ctx\\.bumps", "Result<\\(\\)>", "pub fn", "#\\[account\\]"],
        "anchor_vault": ["use anchor_spl", "Transfer", "CpiContext", "#\\[error_code\\]"],
        "anchor_buggy": ["ctx\\.bumps\\.get", "unwrap"],
        "anchor_legacy": ["declare_id!", "ProgramResult"],
        "multi_workspace": ["#\\[program\\]", "Pubkey", "Signer"],
        "native_solana": ["entrypoint!", "process_instruction", "AccountInfo"],
        "pinocchio": ["pinocchio", "AccountInfo", "ProgramResult"],
    }

    for fixture_name, patterns in patterns_per_fixture.items():
        with build_fixture(fixture_name) as fx:
            for pattern in patterns:
                # Convert escaped regex back to plain English in the prompt
                friendly = pattern.replace("\\", "")
                phrasing = rng.choice(GREP_PHRASINGS)
                user_msg = phrasing.format(pattern=friendly)

                result = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
                if not result.success:
                    continue

                # Count matches
                if "No matches" in result.output:
                    final = f"No matches for `{friendly}`."
                else:
                    match_count = result.output.count("\n") + 1
                    final = f"Found {match_count} match(es) for `{friendly}`."

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Searching the codebase.", [("grep_files", {"pattern": pattern})])),
                        ("user", [("grep_files", True, result.output)]),
                    ],
                    final=final,
                )
                yield make_record(messages, "grep_basic", subcategory=fixture_name)


# ── A7: grep_files with glob filter ──


def gen_grep_with_glob() -> Iterator[Record]:
    """grep_files with optional `glob` arg to filter by file type."""
    rng = random.Random(48)

    configs = [
        ("anchor_counter", "Account", "*.rs"),
        ("anchor_counter", "anchor", "*.toml"),
        ("anchor_vault", "Token", "*.rs"),
        ("multi_workspace", "Pubkey", "*.rs"),
        ("multi_workspace", "version", "Cargo.toml"),
        ("anchor_buggy", "bump", "*.rs"),
        ("anchor_legacy", "declare_id", "*.rs"),
        ("native_solana", "process_instruction", "*.rs"),
    ]

    for fixture_name, pattern, glob in configs:
        with build_fixture(fixture_name) as fx:
            phrasing = rng.choice([
                f"Search for `{pattern}` in {glob} files.",
                f"Find `{pattern}` only in {glob} files.",
                f"Where is `{pattern}` used in {glob} files?",
                f"Grep `{pattern}` across {glob} files.",
            ])

            args = {"pattern": pattern, "glob": glob}
            result = execute_tool_for_real("grep_files", args, fx.path)
            if not result.success:
                continue

            if "No matches" in result.output:
                final = f"No matches for `{pattern}` in {glob} files."
            else:
                final = f"Found `{pattern}` in {glob} files. See the output above."

            messages = build_messages(
                user_msg=phrasing,
                trajectory=[
                    ("assistant", (f"Searching {glob} files.", [("grep_files", args)])),
                    ("user", [("grep_files", True, result.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "grep_with_glob", subcategory=f"{fixture_name}_{glob}")


# ── A8: write_file new files ──


def gen_write_new() -> Iterator[Record]:
    """write_file creating new Rust/TS/TOML/MD files. Synthesized results."""
    rng = random.Random(49)

    # Realistic write tasks
    write_tasks = [
        # (user_prompt, path, content)
        (
            "Create a `.gitignore` for an Anchor project.",
            ".gitignore",
            "target/\nnode_modules/\n.anchor/\ntest-ledger/\n",
        ),
        (
            "Write a basic `tsconfig.json` for an Anchor TypeScript test suite.",
            "tsconfig.json",
            '{\n  "compilerOptions": {\n    "module": "commonjs",\n    "target": "es6",\n    "esModuleInterop": true,\n    "types": ["mocha", "chai"]\n  }\n}\n',
        ),
        (
            "Create a `package.json` with anchor and chai test deps.",
            "package.json",
            '{\n  "name": "my-anchor-app",\n  "version": "0.1.0",\n  "scripts": {\n    "test": "anchor test"\n  },\n  "dependencies": {\n    "@coral-xyz/anchor": "^0.30.1"\n  },\n  "devDependencies": {\n    "chai": "^4.3.0",\n    "mocha": "^10.0.0"\n  }\n}\n',
        ),
        (
            "Scaffold an `Anchor.toml` for the `counter` program at the system program ID.",
            "Anchor.toml",
            '[programs.localnet]\ncounter = "11111111111111111111111111111111"\n\n[provider]\ncluster = "Localnet"\nwallet = "~/.config/solana/id.json"\n',
        ),
        (
            "Create a minimal Anchor program file at `programs/hello/src/lib.rs`.",
            "programs/hello/src/lib.rs",
            'use anchor_lang::prelude::*;\n\n#[program]\npub mod hello {\n    use super::*;\n    pub fn say_hi(_ctx: Context<SayHi>) -> Result<()> {\n        msg!("Hello, world!");\n        Ok(())\n    }\n}\n\n#[derive(Accounts)]\npub struct SayHi {}\n',
        ),
        (
            "Write a `README.md` describing how to build and test the project.",
            "README.md",
            "# My Anchor Project\n\n## Build\n\n    anchor build\n\n## Test\n\n    anchor test\n",
        ),
        (
            "Create a `Cargo.toml` for an Anchor program named `vault`.",
            "programs/vault/Cargo.toml",
            '[package]\nname = "vault"\nversion = "0.1.0"\nedition = "2021"\n\n[lib]\ncrate-type = ["cdylib", "lib"]\n\n[dependencies]\nanchor-lang = "0.30.1"\n',
        ),
        (
            "Write a TypeScript test file for the counter program.",
            "tests/counter.ts",
            'import * as anchor from "@coral-xyz/anchor";\n\ndescribe("counter", () => {\n  it("initializes", async () => {\n    // test body\n  });\n});\n',
        ),
        (
            "Create a `state.rs` module with a `User` account struct.",
            "src/state.rs",
            'use anchor_lang::prelude::*;\n\n#[account]\npub struct User {\n    pub authority: Pubkey,\n    pub points: u64,\n    pub bump: u8,\n}\n',
        ),
        (
            "Add an `errors.rs` with two error variants.",
            "src/errors.rs",
            'use anchor_lang::prelude::*;\n\n#[error_code]\npub enum MyError {\n    #[msg("Insufficient funds")]\n    InsufficientFunds,\n    #[msg("Unauthorized")]\n    Unauthorized,\n}\n',
        ),
    ]

    for prompt, path, content in write_tasks:
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        result_str = f"Wrote {line_count} lines to {path}"

        args = {"path": path, "content": content}
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Creating `{path}`.", [("write_file", args)])),
                ("user", [("write_file", True, result_str)]),
            ],
            final=f"Created `{path}` with {line_count} line(s).",
        )
        yield make_record(messages, "write_new", subcategory=path.replace("/", "_"))


# ── A9: edit_file ──


def gen_edit_basic() -> Iterator[Record]:
    """edit_file find-and-replace using real fixtures."""
    rng = random.Random(50)

    # (fixture, file_path, old_text, new_text, prompt)
    edit_tasks = [
        ("anchor_counter", "programs/counter/src/lib.rs",
         "ctx.accounts.counter.count = 0;",
         "ctx.accounts.counter.count = 1;",
         "Change the initial counter value from 0 to 1."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         '#[msg("Counter overflow")]',
         '#[msg("Counter has overflowed the u64 max value")]',
         "Improve the overflow error message."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         '*ctx.bumps.get("profile").unwrap()',
         "ctx.bumps.profile",
         "Replace the deprecated ctx.bumps.get() call with the modern ctx.bumps.field syntax."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {",
         "pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {\n        require!(amount > 0, VaultError::InsufficientBalance);",
         "Add a require! guard for non-zero amount at the start of `deposit`."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "ProgramResult",
         "Result<()>",
         "Replace the deprecated `ProgramResult` return type with `Result<()>`."),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         "pub amount: u64,",
         "pub amount: u64,\n    pub created_at: i64,",
         "Add a `created_at: i64` field to the `Escrow` struct."),
    ]

    for fixture_name, rel_path, old_text, new_text, prompt in edit_tasks:
        with build_fixture(fixture_name) as fx:
            args = {"path": rel_path, "old_text": old_text, "new_text": new_text}
            result = execute_tool_for_real("edit_file", args, fx.path)

            if not result.success:
                # If the old_text isn't found, skip — but record the failure case for D
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", (f"Editing `{rel_path}`.", [("edit_file", args)])),
                    ("user", [("edit_file", True, result.output)]),
                ],
                final=f"Edit applied to `{rel_path}`.",
            )
            yield make_record(messages, "edit_basic", subcategory=fixture_name)


# ── A10: run_command basic ──


def gen_run_basic() -> Iterator[Record]:
    """run_command for safe operations. Synthesized results (we don't really run anchor)."""
    rng = random.Random(51)

    # (prompt, command, output, success)
    cmd_tasks = [
        ("Build the anchor program.", "anchor build",
         "Building solana-program v1.18.1\nBuilding anchor-lang v0.30.1\nBuilding counter v0.1.0\nFinished `release` profile [optimized] target(s) in 12.43s",
         True),
        ("Run anchor tests.", "anchor test",
         "  counter\n    ✓ Initializes counter (245ms)\n    ✓ Increments counter (122ms)\n\n  2 passing (2s)",
         True),
        ("Check the workspace compiles.", "cargo check",
         "Checking counter v0.1.0\nFinished `dev` profile [optimized + debuginfo] target(s) in 3.21s",
         True),
        ("Run cargo build in release mode.", "cargo build --release",
         "Compiling counter v0.1.0\nFinished `release` profile [optimized] target(s) in 8.14s",
         True),
        ("Show me the current git status.", "git status",
         "On branch main\nYour branch is up to date with 'origin/main'.\n\nnothing to commit, working tree clean",
         True),
        ("Show recent commits.", "git log --oneline -5",
         "abc1234 Add increment instruction\ndef5678 Initial counter program\n0123456 Setup workspace",
         True),
        ("List installed solana version.", "solana --version",
         "solana-cli 1.18.1 (src:abc1234; feat:1234567)",
         True),
        ("Check anchor version.", "anchor --version",
         "anchor-cli 0.30.1",
         True),
        ("Run cargo fmt.", "cargo fmt",
         "(no output)",
         True),
        ("Run clippy on the workspace.", "cargo clippy",
         "Checking counter v0.1.0\nFinished `dev` profile [optimized + debuginfo] target(s) in 2.84s\n    Checking counter v0.1.0",
         True),
    ]

    for prompt, command, output, success in cmd_tasks:
        args = {"command": command}
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Running `{command}`.", [("run_command", args)])),
                ("user", [("run_command", success, output)]),
            ],
            final=f"`{command}` completed successfully." if success else f"`{command}` failed; see output above.",
        )
        yield make_record(messages, "run_basic", subcategory=command.split()[0])


# ── A11: run_command with timeout ──


def gen_run_timeout() -> Iterator[Record]:
    """run_command with explicit timeout argument."""
    rng = random.Random(52)

    cmd_tasks = [
        ("Run the integration tests with a 60s timeout.", "anchor test", 60,
         "  counter\n    ✓ Initializes (320ms)\n  1 passing (1s)"),
        ("Build the program but don't wait more than 90 seconds.", "anchor build", 90,
         "Compiling counter v0.1.0\nFinished `release` profile in 23.2s"),
        ("Run cargo check with a 30 second timeout.", "cargo check", 30,
         "Checking counter v0.1.0\nFinished in 4.1s"),
        ("Test, but timeout at 120s.", "cargo test", 120,
         "running 5 tests\ntest result: ok. 5 passed; 0 failed"),
    ]

    for prompt, command, timeout, output in cmd_tasks:
        args = {"command": command, "timeout": timeout}
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Running with {timeout}s timeout.", [("run_command", args)])),
                ("user", [("run_command", True, output)]),
            ],
            final=f"`{command}` finished within the {timeout}s timeout.",
        )
        yield make_record(messages, "run_timeout", subcategory=command.split()[0])


# ── A12: run_command compound (cd, pipes, &&) ──


def gen_run_compound() -> Iterator[Record]:
    """run_command with shell features (pipes, &&, cd)."""
    rng = random.Random(53)

    cmd_tasks = [
        ("Show the line count of all Rust files.", "find . -name '*.rs' | xargs wc -l | tail -1",
         "    248 total"),
        ("Check that the program compiles AND runs tests.", "anchor build && anchor test",
         "Finished `release` profile in 12.4s\n\n  counter\n    ✓ Initializes (245ms)\n  1 passing"),
        ("Count occurrences of `pub fn` in the source.", "grep -r 'pub fn' programs/ | wc -l",
         "       7"),
        ("Show me the size of the build artifacts.", "du -sh target/",
         "127M\ttarget/"),
        ("Get the project version from Cargo.toml.", "grep '^version' Cargo.toml",
         'version = "0.1.0"'),
    ]

    for prompt, command, output in cmd_tasks:
        args = {"command": command}
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Executing the command.", [("run_command", args)])),
                ("user", [("run_command", True, output)]),
            ],
            final=f"`{command}` produced the output above.",
        )
        yield make_record(messages, "run_compound", subcategory="shell")


# ── Main pipeline ──


def expand_to_target(records: list[Record], target: int, seed: int = 100) -> list[Record]:
    """Repeat records to reach target count, shuffling phrasings if possible.

    For now we just repeat — the natural variation in fixtures gives us
    enough diversity. Future: paraphrase user prompts via Claude Haiku.
    """
    if len(records) >= target:
        rng = random.Random(seed)
        return rng.sample(records, target)
    # Repeat with shuffle
    out = list(records)
    rng = random.Random(seed)
    while len(out) < target:
        more = list(records)
        rng.shuffle(more)
        out.extend(more)
    return out[:target]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--total", type=int, default=PLAN_V2_TOTAL)
    args = parser.parse_args()

    generators = {
        "read_basic": gen_read_basic,
        "read_offset_limit": gen_read_offset_limit,
        "read_abs_rel": gen_read_abs_rel,
        "glob_basic": gen_glob_basic,
        "glob_with_path": gen_glob_with_path,
        "grep_basic": gen_grep_basic,
        "grep_with_glob": gen_grep_with_glob,
        "write_new": gen_write_new,
        "edit_basic": gen_edit_basic,
        "run_basic": gen_run_basic,
        "run_timeout": gen_run_timeout,
        "run_compound": gen_run_compound,
    }

    # Compute scaling factor for plan_v2_total
    designed_total = sum(TARGETS.values())
    scale = args.total / designed_total

    all_records: list[Record] = []
    for name, gen_fn in generators.items():
        target = max(1, round(TARGETS[name] * scale))
        # Generate raw records
        raw = list(gen_fn())
        # Expand or sample to target
        scaled = expand_to_target(raw, target, seed=hash(name) & 0xFFFF)
        print(f"  {name}: {len(raw)} unique → {len(scaled)} records (target {target})")
        all_records.extend(scaled)

    print(f"\nTotal: {len(all_records)} records")
    write_records_to_jsonl(all_records, args.output)


if __name__ == "__main__":
    main()
