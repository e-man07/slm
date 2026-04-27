"""Groups G + H + I: Parser edge cases, iteration control, tool-result reasoning (target: 1,500).

  G — Parser edge cases (500): teach the model to emit canonical format under
  every condition the parser tolerates. The parser handles repair (single quotes,
  trailing commas, missing braces) — but we DO NOT teach those broken forms.
  We teach the canonical strict form everywhere.

  H — Iteration control (200): long trajectories that finish cleanly, plus
  graceful give-up before max iterations.

  I — Tool-result reasoning (800): reading output, branching on grep results,
  diagnosing cargo errors, working with truncated output.

Subcategories:
  G1 Multiple tool_call tags in one assistant turn      (80)
  G2 Complex args with escaped quotes                   (80)
  G3 Multiline JSON inside <tool_call>                  (80)
  G5 Prose before AND after tool tag                    (100)
  G7 Mention <tool_call> in prose without invocation    (40)
  G8 Rust/json blocks AND tool_call in same response    (80)
  G9 Canonical "arguments" key (no parameters variant)  (40)

  H1 10-14 step trajectories, finish cleanly            (80)
  H2 Tasks completing in 2-4 iterations                 (80)
  H3 Graceful give-up before max iterations             (40)

  I1 Read result → summarize file purpose               (200)
  I2 Grep result with 0/1/many matches → adapt          (200)
  I3 Cargo error output → identify line → fix           (200)
  I4 Truncated output → narrow next call                (100)
  I5 Multiple tool_results in one user turn → reason    (100)

Total = 1,500.
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
    make_tool_call,
    system_prompt,
    write_records_to_jsonl,
)
from gen_tool_fixtures import build_fixture
from schema import Record

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "sft_tool_calling_edge_cases.jsonl"

PLAN_TARGET = 1_500

TARGETS = {
    "G1_multi_tool_calls": 80,
    "G2_escaped_quotes": 80,
    "G3_multiline_json": 80,
    "G5_prose_sandwich": 100,
    "G7_tool_mentioned_in_prose": 40,
    "G8_blocks_and_tool_call": 80,
    "G9_canonical_arguments": 40,
    "H1_long_trajectory": 80,
    "H2_normal_completion": 80,
    "H3_graceful_giveup": 40,
    "I1_summarize_file": 200,
    "I2_branch_on_grep": 200,
    "I3_diagnose_cargo": 200,
    "I4_truncated_output": 100,
    "I5_cross_result_reasoning": 100,
}


# ── G1: Multiple tool calls in one turn ──


def gen_G1_multi_tool_calls() -> Iterator[Record]:
    cases = [
        ("multi_workspace", ["programs/escrow/src/lib.rs", "programs/oracle/src/lib.rs"],
         "Read both program files."),
        ("anchor_counter", ["Anchor.toml", "Cargo.toml"],
         "Read both manifests."),
    ]
    for fixture, paths, prompt in cases:
        with build_fixture(fixture) as fx:
            calls = []
            results = []
            for p in paths:
                r = execute_tool_for_real("read_file", {"path": p}, fx.path)
                if r.success:
                    calls.append(("read_file", {"path": p}))
                    results.append(("read_file", True, r.output))
            if len(calls) < 2:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading both files.", calls)),
                    ("user", results),
                ],
                final=f"Read {len(calls)} files; contents above.",
            )
            yield make_record(messages, "G1_multi_tool_calls", subcategory=fixture)


# ── G2: Complex args with escaped quotes ──


def gen_G2_escaped_quotes() -> Iterator[Record]:
    """write_file with content containing both single and double quotes — JSON serialization handles escaping."""
    cases = [
        (
            "Write a Rust file with `println!(\"hello {}\", name)`.",
            "src/main.rs",
            'fn main() {\n    let name = "world";\n    println!("hello {}", name);\n}\n',
            "Created `src/main.rs` with a `println!` macro using both string formatting and double quotes.",
        ),
        (
            "Create a JSON config with both 'single' and \"double\" quotes in a comment.",
            "config.json",
            '{\n  "_comment": "uses \'single\' and \\"double\\" quotes",\n  "name": "test"\n}\n',
            "Config written; the comment contains both quote types properly escaped.",
        ),
        (
            "Add a Rust string with embedded quotes.",
            "src/lib.rs",
            'pub const MOTTO: &str = "He said \\"hi\\" to me";\n',
            "Wrote a string constant with escaped inner double quotes.",
        ),
    ]
    for prompt, path, content, final in cases:
        line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Creating `{path}`.", [("write_file", {"path": path, "content": content})])),
                ("user", [("write_file", True, f"Wrote {line_count} lines to {path}")]),
            ],
            final=final,
        )
        yield make_record(messages, "G2_escaped_quotes", subcategory=path.replace("/", "_"))


# ── G3: Multiline JSON ──


def gen_G3_multiline_json() -> Iterator[Record]:
    """write_file with a long content arg — naturally produces multiline JSON tool calls."""
    cases = [
        ("Write a complete Anchor lib.rs for a token vault.",
         "programs/vault/src/lib.rs",
         "use anchor_lang::prelude::*;\nuse anchor_spl::token::{Token, TokenAccount, Transfer, transfer};\n\n"
         "#[program]\npub mod vault {\n    use super::*;\n    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {\n"
         "        let cpi_accounts = Transfer {\n            from: ctx.accounts.user_token.to_account_info(),\n"
         "            to: ctx.accounts.vault_token.to_account_info(),\n            authority: ctx.accounts.user.to_account_info(),\n"
         "        };\n        let cpi_ctx = CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts);\n"
         "        transfer(cpi_ctx, amount)?;\n        Ok(())\n    }\n}\n\n"
         "#[derive(Accounts)]\npub struct Deposit<'info> {\n    #[account(mut)]\n    pub user_token: Account<'info, TokenAccount>,\n"
         "    #[account(mut)]\n    pub vault_token: Account<'info, TokenAccount>,\n    pub user: Signer<'info>,\n"
         "    pub token_program: Program<'info, Token>,\n}\n",
         "Created `programs/vault/src/lib.rs` with the `Deposit` instruction and SPL Token CPI."),
    ]
    for prompt, path, content, final in cases:
        line_count = content.count("\n")
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Writing the program file.", [("write_file", {"path": path, "content": content})])),
                ("user", [("write_file", True, f"Wrote {line_count} lines to {path}")]),
            ],
            final=final,
        )
        yield make_record(messages, "G3_multiline_json", subcategory="long_content")


# ── G5: Prose sandwich (prose before and after tool tag in same turn) ──


def gen_G5_prose_sandwich() -> Iterator[Record]:
    """Assistant turns with multiple tool calls separated by prose."""
    # NOTE: per training invariant, tool-call turns shouldn't end with prose AFTER the call.
    # But MULTIPLE calls separated by short prose is fine. Skip this — covered by G1.
    # Instead, this category teaches: "I'll do X first" + tool, AS the canonical pattern.
    cases = [
        ("Find and read all Rust source files.", "multi_workspace"),
    ]
    for prompt, fixture in cases:
        with build_fixture(fixture) as fx:
            glob_r = execute_tool_for_real("glob_files", {"pattern": "**/*.rs"}, fx.path)
            if not glob_r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("First, let me list the Rust files. Then I'll read each.",
                                   [("glob_files", {"pattern": "**/*.rs"})])),
                    ("user", [("glob_files", True, glob_r.output)]),
                ],
                final="Found the files above; ready to read any one of them on request.",
            )
            yield make_record(messages, "G5_prose_sandwich", subcategory=fixture)


# ── G7: Mention <tool_call> in prose without invoking ──


def gen_G7_tool_mentioned_in_prose() -> Iterator[Record]:
    """Assistant explains how a tool would be used without actually calling it (e.g., conceptual)."""
    cases = [
        ("How does the read_file tool work?",
         "The `read_file` tool takes a `path` argument (required) and optional `offset`/`limit` for paginated reads. "
         "It returns the file's contents with line numbers. For example, you'd invoke it like calling read_file with "
         "{\"path\": \"src/lib.rs\"} — but I'm not running it now since you only asked how it works."),
        ("Walk me through what happens when I ask you to grep for something.",
         "Sure. When you ask me to find a pattern, I invoke `grep_files` with the regex pattern (and optional `path` "
         "and `glob` filter). The tool runs the search and returns matching lines with file:line:content format. "
         "I then read the results to give you a summary or use them as input for a next step."),
    ]
    for prompt, response in cases:
        messages = [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response},
        ]
        yield make_record(messages, "G7_tool_mentioned_in_prose", subcategory="conceptual")


# ── G8: Rust code blocks alongside tool calls ──


def gen_G8_blocks_and_tool_call() -> Iterator[Record]:
    """Assistant follows a tool result with a final response that includes a ```rust``` block."""
    cases = [
        ("Read programs/counter/src/lib.rs and give me a snippet showing the increment instruction.",
         "anchor_counter", "programs/counter/src/lib.rs",
         "Here's the `increment` handler:\n\n"
         "```rust\npub fn increment(ctx: Context<Increment>) -> Result<()> {\n"
         "    ctx.accounts.counter.count = ctx.accounts.counter.count\n"
         "        .checked_add(1)\n"
         "        .ok_or(ErrorCode::Overflow)?;\n"
         "    Ok(())\n}\n```\n\n"
         "It uses `checked_add` to prevent overflow, returning `ErrorCode::Overflow` if it does."),
    ]
    for prompt, fixture, path, final in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("read_file", {"path": path}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading.", [("read_file", {"path": path})])),
                    ("user", [("read_file", True, r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "G8_blocks_and_tool_call", subcategory=fixture)


# ── G9: Canonical arguments key ──


def gen_G9_canonical_arguments() -> Iterator[Record]:
    """All our generators emit "arguments" (not "parameters"). This category just reinforces it."""
    cases = [
        ("Just read Cargo.toml.", "anchor_counter", "Cargo.toml"),
    ]
    for prompt, fixture, path in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("read_file", {"path": path}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading.", [("read_file", {"path": path})])),
                    ("user", [("read_file", True, r.output)]),
                ],
                final="Done.",
            )
            yield make_record(messages, "G9_canonical_arguments", subcategory=fixture)


# ── H1: Long trajectory (10-14 steps) ──


def gen_H1_long_trajectory() -> Iterator[Record]:
    """Long task: scaffold + verify + edit + verify."""
    files = [
        ("Cargo.toml", '[workspace]\nmembers = ["programs/*"]\n'),
        ("Anchor.toml", '[programs.localnet]\napp = "11111111111111111111111111111111"\n'),
        ("programs/app/Cargo.toml", '[package]\nname = "app"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\nanchor-lang = "0.30.1"\n'),
        ("programs/app/src/lib.rs", 'use anchor_lang::prelude::*;\n\n#[program]\npub mod app {\n    use super::*;\n    pub fn init(_ctx: Context<Init>) -> Result<()> { Ok(()) }\n}\n\n#[derive(Accounts)]\npub struct Init {}\n'),
    ]

    trajectory = []
    for path, content in files:
        line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
        trajectory.append(("assistant", (f"Creating `{path}`.", [("write_file", {"path": path, "content": content})])))
        trajectory.append(("user", [("write_file", True, f"Wrote {line_count} lines to {path}")]))

    # Verify: glob → read → run check
    trajectory.append(("assistant", ("Verifying file structure.", [("glob_files", {"pattern": "**/*.rs"})])))
    trajectory.append(("user", [("glob_files", True, "1 files found:\nprograms/app/src/lib.rs")]))

    trajectory.append(("assistant", ("Running cargo check.", [("run_command", {"command": "cargo check"})])))
    trajectory.append(("user", [("run_command", True, "Checking app v0.1.0\nFinished in 4.2s")]))

    messages = build_messages(
        user_msg="Scaffold a basic Anchor program named `app` and verify it compiles.",
        trajectory=trajectory,
        final="Scaffold complete. Created 4 files; `cargo check` passes.",
    )
    yield make_record(messages, "H1_long_trajectory", subcategory="full_scaffold")


# ── H2: Normal 2-4 iteration completion ──


def gen_H2_normal_completion() -> Iterator[Record]:
    cases = [
        ("Read Anchor.toml.", "anchor_counter", "Anchor.toml"),
        ("Show me Cargo.toml.", "anchor_counter", "Cargo.toml"),
    ]
    for prompt, fixture, path in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("read_file", {"path": path}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading.", [("read_file", {"path": path})])),
                    ("user", [("read_file", True, r.output)]),
                ],
                final="Done.",
            )
            yield make_record(messages, "H2_normal_completion", subcategory=fixture)


# ── H3: Graceful give-up ──


def gen_H3_graceful_giveup() -> Iterator[Record]:
    cases = [
        ("Find every place we override the default rent calculation.",
         "anchor_counter",
         "I searched for `Rent::get`, `rent::minimum_balance`, and `lamports`. None of those patterns appear in the "
         "counter program — it uses Anchor's default `init` constraint to compute rent automatically. There's "
         "nothing to find here. If you want to override rent calculation, you'd need to manually call "
         "`Rent::get()?.minimum_balance(N)` somewhere in the code, but that's not present."),
    ]
    for prompt, fixture, final in cases:
        with build_fixture(fixture) as fx:
            r1 = execute_tool_for_real("grep_files", {"pattern": "Rent::get"}, fx.path)
            r2 = execute_tool_for_real("grep_files", {"pattern": "rent::minimum"}, fx.path)
            r3 = execute_tool_for_real("grep_files", {"pattern": "lamports"}, fx.path)
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Searching for rent-related code.", [("grep_files", {"pattern": "Rent::get"})])),
                    ("user", [("grep_files", True, r1.output)]),
                    ("assistant", ("Trying minimum_balance.", [("grep_files", {"pattern": "rent::minimum"})])),
                    ("user", [("grep_files", True, r2.output)]),
                    ("assistant", ("Last attempt: searching for lamports.", [("grep_files", {"pattern": "lamports"})])),
                    ("user", [("grep_files", True, r3.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "H3_graceful_giveup", subcategory=fixture)


# ── I1: Summarize file ──


def gen_I1_summarize_file() -> Iterator[Record]:
    cases = [
        ("anchor_counter", "programs/counter/src/lib.rs",
         "Read this and tell me the program's structure.",
         "It's a minimal Anchor program with two instructions:\n\n"
         "1. **`initialize`** — creates a counter PDA, stores `count=0`, `authority=user`, `bump`.\n"
         "2. **`increment`** — bumps `count` with overflow check, gated by `has_one = authority`.\n\n"
         "PDA seeds: `[\"counter\", user_pubkey]`. Storage: `Counter { count, authority, bump }`."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "What is this program doing?",
         "A token vault with a `deposit` instruction. It CPIs into the SPL Token program (`anchor_spl::token::transfer`) "
         "to move tokens from the user's token account to the vault's token account. The user signs as the source authority."),
    ]
    for fixture, path, prompt, final in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("read_file", {"path": path}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading.", [("read_file", {"path": path})])),
                    ("user", [("read_file", True, r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "I1_summarize_file", subcategory=fixture)


# ── I2: Branch on grep results ──


def gen_I2_branch_on_grep() -> Iterator[Record]:
    """grep returns 0/1/many matches → assistant adapts next step."""
    cases = [
        ("Find any uses of declare_id! and remove them.",
         "anchor_legacy", "declare_id!", "programs/legacy/src/lib.rs",
         'declare_id!("Fg6PaFpoGXkKXx2KcD684s5rJNHHk3JG462ZiJxkZuFZ");',
         '// Program ID is set in Anchor.toml',
         "Found one occurrence in `programs/legacy/src/lib.rs`. Removed it; the program ID is now declared in `Anchor.toml`."),
    ]
    for prompt, fixture, pattern, rel_path, old_t, new_t, final in cases:
        with build_fixture(fixture) as fx:
            grep_r = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
            edit_r = execute_tool_for_real("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t}, fx.path)
            if not (grep_r.success and edit_r.success):
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("First, finding occurrences.", [("grep_files", {"pattern": pattern})])),
                    ("user", [("grep_files", True, grep_r.output)]),
                    ("assistant", ("One match — removing it.", [("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t})])),
                    ("user", [("edit_file", True, edit_r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "I2_branch_on_grep", subcategory=fixture)


# ── I3: Diagnose cargo error ──


def gen_I3_diagnose_cargo() -> Iterator[Record]:
    """Run cargo, see error, identify the line, navigate to it."""
    cases = [
        ("Build the program.", "anchor_buggy", "cargo check",
         "Exit code 101\nerror[E0599]: no method named `get` found for struct `Bumps` in the current scope\n"
         "  --> programs/buggy/src/lib.rs:8:32\n"
         "   |\n"
         "8  |         ctx.accounts.profile.bump = *ctx.bumps.get(\"profile\").unwrap();\n"
         "   |                                                ^^^",
         "programs/buggy/src/lib.rs",
         "The error is in `programs/buggy/src/lib.rs:8`. The code uses `ctx.bumps.get(\"profile\")` which is the "
         "deprecated Anchor 0.29 API. In 0.30+, `ctx.bumps` is a struct with field access (`ctx.bumps.profile`). "
         "Reading the file confirms — line 8 needs to change from `*ctx.bumps.get(\"profile\").unwrap()` to "
         "`ctx.bumps.profile`."),
    ]
    for prompt, fixture, cmd, err, rel_path, final in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Building.", [("run_command", {"command": cmd})])),
                    ("user", [("run_command", False, err)]),
                    ("assistant", (f"Reading the file at the error line.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "I3_diagnose_cargo", subcategory=fixture)


# ── I4: Truncated output ──


def gen_I4_truncated_output() -> Iterator[Record]:
    cases = [
        ("Show me cargo's verbose output.", "cargo build -vv",
         "[long verbose build output...]\n... (truncated)",
         "cargo build", "Compiling foo v0.1.0\nFinished `release` profile in 12.4s",
         "The verbose output exceeded the 64KB cap and was truncated. For a normal build summary, regular "
         "`cargo build` is sufficient."),
    ]
    for prompt, cmd1, out1_truncated, cmd2, out2, final in cases:
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Running verbose.", [("run_command", {"command": cmd1})])),
                ("user", [("run_command", True, out1_truncated)]),
                ("assistant", ("Output too large — re-running without -vv.", [("run_command", {"command": cmd2})])),
                ("user", [("run_command", True, out2)]),
            ],
            final=final,
        )
        yield make_record(messages, "I4_truncated_output", subcategory="verbose_cap")


# ── I5: Cross-result reasoning (multiple tool_results in one user turn) ──


def gen_I5_cross_result_reasoning() -> Iterator[Record]:
    cases = [
        ("multi_workspace",
         ["programs/escrow/src/lib.rs", "programs/oracle/src/lib.rs"],
         "Read both program files and tell me which one has authority gating.",
         "The **oracle** uses `has_one = authority` for access control on `update`. The **escrow** doesn't have "
         "an authority field — anyone holding the maker's keypair can sign for the PDA but there's no separate "
         "authority check. The oracle is more access-controlled; the escrow relies on PDA seeds for ownership."),
    ]
    for fixture, paths, prompt, final in cases:
        with build_fixture(fixture) as fx:
            calls = []
            results = []
            for p in paths:
                r = execute_tool_for_real("read_file", {"path": p}, fx.path)
                if r.success:
                    calls.append(("read_file", {"path": p}))
                    results.append(("read_file", True, r.output))
            if len(calls) < 2:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading both at once.", calls)),
                    ("user", results),
                ],
                final=final,
            )
            yield make_record(messages, "I5_cross_result_reasoning", subcategory=fixture)


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
        "G1_multi_tool_calls": gen_G1_multi_tool_calls,
        "G2_escaped_quotes": gen_G2_escaped_quotes,
        "G3_multiline_json": gen_G3_multiline_json,
        "G5_prose_sandwich": gen_G5_prose_sandwich,
        "G7_tool_mentioned_in_prose": gen_G7_tool_mentioned_in_prose,
        "G8_blocks_and_tool_call": gen_G8_blocks_and_tool_call,
        "G9_canonical_arguments": gen_G9_canonical_arguments,
        "H1_long_trajectory": gen_H1_long_trajectory,
        "H2_normal_completion": gen_H2_normal_completion,
        "H3_graceful_giveup": gen_H3_graceful_giveup,
        "I1_summarize_file": gen_I1_summarize_file,
        "I2_branch_on_grep": gen_I2_branch_on_grep,
        "I3_diagnose_cargo": gen_I3_diagnose_cargo,
        "I4_truncated_output": gen_I4_truncated_output,
        "I5_cross_result_reasoning": gen_I5_cross_result_reasoning,
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
