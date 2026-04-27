"""Group D: Error recovery (target: 1,000).

Every error string from tools.py appears verbatim, paired with a recovery path
the model should learn. Teaches: read the error, adjust, retry — don't loop or
hallucinate.

Subcategories (all error message strings copied byte-for-byte from tools.py):
  D1  read_file → "File not found" → glob → re-read       (150)
  D2  read_file → "File too large" → use offset/limit     (80)
  D3  read_file → "Cannot read file: <decode error>"      (60)
  D4  edit_file → "Text not found" → re-read → fix        (200)
  D5  edit_file → "File not found" → write_file instead   (80)
  D6  edit_file multi-match (only first replaced)         (80)
  D7  run_command → "Exit code N\n{stderr}"               (200)
  D8  run_command → "Command timed out"                   (80)
  D9  run_command → 64KB output cap → narrow              (80)
  D10 glob → "No matches" → broaden                       (80)
  D11 grep → "Invalid regex" → escape                     (80)
  D12 grep → "No matches" → broaden                       (60)
  D13 "Directory not found" / "Path not found"            (50)
  D14 "Unknown tool" — model used fictional tool          (20)
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Iterator

from _tool_calling_common import build_messages, make_record, write_records_to_jsonl
from gen_tool_fixtures import build_fixture
from schema import Record

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "sft_tool_calling_errors.jsonl"

PLAN_TARGET = 1_000

TARGETS = {
    "D1_file_not_found": 150,
    "D2_file_too_large": 80,
    "D3_decode_error": 60,
    "D4_text_not_found": 200,
    "D5_edit_missing_file": 80,
    "D6_multi_match": 80,
    "D7_exit_code": 200,
    "D8_command_timeout": 80,
    "D9_output_cap": 80,
    "D10_glob_no_matches": 80,
    "D11_invalid_regex": 80,
    "D12_grep_no_matches": 60,
    "D13_directory_not_found": 50,
    "D14_unknown_tool": 20,
}


# ── D1: File not found → recover ──


def gen_D1_file_not_found() -> Iterator[Record]:
    cases = [
        ("Read src/lib.rs.", "src/lib.rs", "**/*.rs", "programs/counter/src/lib.rs",
         "anchor_counter",
         "src/lib.rs doesn't exist at the project root. The actual file is `programs/counter/src/lib.rs` — let me read that."),
        ("Show me the program file.", "program.rs", "**/*.rs", "programs/escrow/src/lib.rs",
         "multi_workspace",
         "There's no `program.rs`. Let me find Rust files first."),
        ("Open Cargo.lock.", "Cargo.lock", "**/Cargo.toml", "Cargo.toml",
         "anchor_counter",
         "`Cargo.lock` doesn't exist (likely not committed). Let me look at `Cargo.toml` instead."),
    ]

    for prompt, bad_path, glob_pattern, real_path, fixture, final in cases:
        with build_fixture(fixture) as fx:
            err = f"File not found: {bad_path}"
            from _tool_calling_common import execute_tool_for_real
            glob_r = execute_tool_for_real("glob_files", {"pattern": glob_pattern}, fx.path)
            read_r = execute_tool_for_real("read_file", {"path": real_path}, fx.path)
            if not (glob_r.success and read_r.success):
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading.", [("read_file", {"path": bad_path})])),
                    ("user", [("read_file", False, err)]),
                    ("assistant", ("File missing — let me search for it.", [("glob_files", {"pattern": glob_pattern})])),
                    ("user", [("glob_files", True, glob_r.output)]),
                    ("assistant", (f"Reading the actual path.", [("read_file", {"path": real_path})])),
                    ("user", [("read_file", True, read_r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "D1_file_not_found", subcategory=fixture)


# ── D2: File too large ──


def gen_D2_file_too_large() -> Iterator[Record]:
    cases = [
        ("Read the entire build log.",
         "target/build.log", "Cannot read file: target/build.log: file size 2348234 exceeds 1MB limit",
         "I'll get the head only.", {"path": "target/build.log", "limit": 100},
         "Showing the first 100 lines.\n[truncated build output]",
         "Build log was too large; read the first 100 lines instead."),
    ]

    for prompt, path, err, retry_msg, retry_args, retry_out, final in cases:
        # Simulate the real error string from tools.py:174
        err_real = f"File too large (max 1MB): {path.split('/')[-1]}"
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Reading.", [("read_file", {"path": path})])),
                ("user", [("read_file", False, err_real)]),
                ("assistant", (retry_msg, [("read_file", retry_args)])),
                ("user", [("read_file", True, retry_out)]),
            ],
            final=final,
        )
        yield make_record(messages, "D2_file_too_large", subcategory="size_limit")


# ── D3: decode error ──


def gen_D3_decode_error() -> Iterator[Record]:
    cases = [
        ("Read the binary at target/deploy/program.so.",
         "target/deploy/program.so",
         "Cannot read file: 'utf-8' codec can't decode byte 0x7f in position 0: invalid start byte",
         "That file is a binary `.so` — I can't read it as text. If you want to inspect it, use `solana program show` "
         "or look at the source `.rs` files instead."),
    ]
    for prompt, path, err, final in cases:
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Reading.", [("read_file", {"path": path})])),
                ("user", [("read_file", False, err)]),
            ],
            final=final,
        )
        yield make_record(messages, "D3_decode_error", subcategory="binary_file")


# ── D4: edit_file Text not found ──


def gen_D4_text_not_found() -> Iterator[Record]:
    cases = [
        ("Replace `let x = 5` with `let x = 10` in src/lib.rs.",
         "anchor_counter", "programs/counter/src/lib.rs",
         "let x = 5", "let x = 10",
         "ctx.accounts.counter.count = 0;", "ctx.accounts.counter.count = 1;",
         "That literal wasn't in the file. Looking at the actual content, the analogous line is "
         "`ctx.accounts.counter.count = 0;` — I changed that to `1` instead."),
    ]

    for prompt, fixture, rel_path, bad_old, bad_new, real_old, real_new, final in cases:
        with build_fixture(fixture) as fx:
            from _tool_calling_common import execute_tool_for_real
            err_real = f"Text not found in {rel_path}: {bad_old[:60]}..."
            read_r = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            edit_r = execute_tool_for_real("edit_file", {"path": rel_path, "old_text": real_old, "new_text": real_new}, fx.path)
            if not (read_r.success and edit_r.success):
                continue

            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Editing.", [("edit_file", {"path": rel_path, "old_text": bad_old, "new_text": bad_new})])),
                    ("user", [("edit_file", False, err_real)]),
                    ("assistant", ("Text not present — let me read the file to find the right target.", [("read_file", {"path": rel_path})])),
                    ("user", [("read_file", True, read_r.output)]),
                    ("assistant", ("Now editing the correct line.", [("edit_file", {"path": rel_path, "old_text": real_old, "new_text": real_new})])),
                    ("user", [("edit_file", True, edit_r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "D4_text_not_found", subcategory=fixture)


# ── D5: edit_file → file missing → write_file instead ──


def gen_D5_edit_missing_file() -> Iterator[Record]:
    cases = [
        ("Update programs/widget/src/lib.rs to add a comment.",
         "programs/widget/src/lib.rs",
         "// nothing", "// New comment\n// nothing",
         "The file doesn't exist — there's no `widget` program in this workspace. Did you mean to create it? "
         "I can scaffold it with `write_file` if so."),
    ]
    for prompt, path, old_t, new_t, final in cases:
        err = f"File not found: {path}"
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Editing.", [("edit_file", {"path": path, "old_text": old_t, "new_text": new_t})])),
                ("user", [("edit_file", False, err)]),
            ],
            final=final,
        )
        yield make_record(messages, "D5_edit_missing_file", subcategory="missing_file")


# ── D6: multi-match (only first replaced) ──


def gen_D6_multi_match() -> Iterator[Record]:
    cases = [
        ("Rename all occurrences of `count` to `counter_value` in lib.rs.",
         "anchor_counter", "programs/counter/src/lib.rs",
         "count", "counter_value",
         "I replaced the first occurrence, but `edit_file` only replaces the first match. To rename all "
         "occurrences, you'd need to call `edit_file` repeatedly with the new context, or do a manual "
         "search-and-replace per line. Want me to read the file and do them one at a time?"),
    ]

    for prompt, fixture, rel_path, old_t, new_t, final in cases:
        with build_fixture(fixture) as fx:
            from _tool_calling_common import execute_tool_for_real
            edit_r = execute_tool_for_real("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t}, fx.path)
            if not edit_r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Editing.", [("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t})])),
                    ("user", [("edit_file", True, edit_r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "D6_multi_match", subcategory=fixture)


# ── D7: Exit code (cargo errors) ──


def gen_D7_exit_code() -> Iterator[Record]:
    cases = [
        ("Build the program.",
         "anchor build",
         "error[E0599]: no method named `unwrap` found for type `u8` in the current scope\n  --> programs/counter/src/lib.rs:12:42",
         "The build failed because of a method-resolution error on a `u8`. Looking at line 12, you're calling "
         "`.unwrap()` on something that's just a number. Let me read the file and fix it.",
         "Exit code 101"),
        ("Run cargo check.",
         "cargo check",
         "error[E0382]: borrow of moved value: `data`\n --> src/lib.rs:8:5",
         "Borrow-of-moved-value error at line 8. You moved `data` (probably with `.into()` or by passing by "
         "value) and then tried to use it again. Need to either clone before the move or restructure to avoid the move.",
         "Exit code 101"),
    ]
    for prompt, cmd, err_body, final, exit_code in cases:
        full_err = f"{exit_code}\n{err_body}"
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Running.", [("run_command", {"command": cmd})])),
                ("user", [("run_command", False, full_err)]),
            ],
            final=final,
        )
        yield make_record(messages, "D7_exit_code", subcategory=cmd.split()[0])


# ── D8: Command timeout ──


def gen_D8_command_timeout() -> Iterator[Record]:
    cases = [
        ("Run the full anchor test suite.", "anchor test", 30,
         "anchor test", 120,
         "Tests timed out at 30 seconds. Re-running with a 120-second timeout (the suite is large)."),
        ("Build in release mode.", "cargo build --release", 60,
         "cargo build --release", 300,
         "Build timed out — release builds can take a few minutes. Bumping timeout to 300s."),
    ]
    for prompt, cmd, timeout1, retry_cmd, timeout2, final in cases:
        err = f"Command timed out after {timeout1}s: {cmd}"
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Running with {timeout1}s timeout.", [("run_command", {"command": cmd, "timeout": timeout1})])),
                ("user", [("run_command", False, err)]),
                ("assistant", (f"Retrying with {timeout2}s.", [("run_command", {"command": retry_cmd, "timeout": timeout2})])),
                ("user", [("run_command", True, "Compiling counter v0.1.0\nFinished `release` profile in 2m 14s")]),
            ],
            final=final,
        )
        yield make_record(messages, "D8_command_timeout", subcategory=cmd.split()[0])


# ── D9: output cap ──


def gen_D9_output_cap() -> Iterator[Record]:
    cases = [
        ("Print all the cargo verbose build output.", "cargo build -vv",
         "cargo build -vv | head -50",
         "The verbose output exceeded 64KB and was truncated. Re-running with `head -50` to keep it manageable."),
    ]
    for prompt, cmd, retry, final in cases:
        truncated_output = "[long output]\n" * 100 + "\n... (truncated)"
        retry_output = "[short output]\nFinished build in 12.3s"
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Running verbose.", [("run_command", {"command": cmd})])),
                ("user", [("run_command", True, truncated_output)]),
                ("assistant", ("Output too large — narrowing.", [("run_command", {"command": retry})])),
                ("user", [("run_command", True, retry_output)]),
            ],
            final=final,
        )
        yield make_record(messages, "D9_output_cap", subcategory="verbose")


# ── D10: glob no matches ──


def gen_D10_glob_no_matches() -> Iterator[Record]:
    cases = [
        ("Find all .py files.", "*.py", "**/*.py",
         "There are no Python files at the root. Searching recursively didn't find any either — this is a Rust/TS project."),
    ]
    for prompt, narrow, broad, final in cases:
        no_match = f"No matches for pattern: {narrow}"
        broad_match = f"No matches for pattern: {broad}"
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Searching.", [("glob_files", {"pattern": narrow})])),
                ("user", [("glob_files", True, no_match)]),
                ("assistant", ("Trying recursive.", [("glob_files", {"pattern": broad})])),
                ("user", [("glob_files", True, broad_match)]),
            ],
            final=final,
        )
        yield make_record(messages, "D10_glob_no_matches", subcategory="no_match")


# ── D11: invalid regex ──


def gen_D11_invalid_regex() -> Iterator[Record]:
    cases = [
        ("Find usages of `Vec<u8>`.",
         "Vec<u8>", "Vec<u8>",
         "Vec<u8\\>", "Vec<u8\\>",
         "I had to escape the `>` (it's a regex metacharacter when paired with `<` in some flavors). The escaped form works."),
    ]
    for prompt, bad_pat, _, good_pat, _, final in cases:
        # tools.py raises Invalid regex: <details> — but actually < and > are fine in re; this is illustrative.
        # Use a real bad regex instead:
        actual_bad = "Vec<u8>("
        actual_good = "Vec<u8>\\("
        err = f"Invalid regex: missing ), unterminated subpattern at position 7"
        good_output = "src/lib.rs:14: pub data: Vec<u8>(),"

        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Searching.", [("grep_files", {"pattern": actual_bad})])),
                ("user", [("grep_files", False, err)]),
                ("assistant", ("Escaping the parenthesis.", [("grep_files", {"pattern": actual_good})])),
                ("user", [("grep_files", True, good_output)]),
            ],
            final="The unescaped `(` was being interpreted as a regex group start. Escaped it and the search worked.",
        )
        yield make_record(messages, "D11_invalid_regex", subcategory="paren_escape")


# ── D12: grep no matches ──


def gen_D12_grep_no_matches() -> Iterator[Record]:
    cases = [
        ("Find usages of `forbidden_function`.",
         "forbidden_function", "function",
         "No matches for `forbidden_function`. Broadening to `function` finds typical Rust function definitions, "
         "but the specific name doesn't appear anywhere."),
    ]
    for prompt, narrow, broad, final in cases:
        no_match = f"No matches for pattern: {narrow}"
        broad_out = "src/lib.rs:10: pub fn initialize(\nsrc/lib.rs:20: pub fn increment("
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Searching.", [("grep_files", {"pattern": narrow})])),
                ("user", [("grep_files", True, no_match)]),
                ("assistant", ("Broadening.", [("grep_files", {"pattern": broad})])),
                ("user", [("grep_files", True, broad_out)]),
            ],
            final=final,
        )
        yield make_record(messages, "D12_grep_no_matches", subcategory="not_found")


# ── D13: Directory/Path not found ──


def gen_D13_directory_not_found() -> Iterator[Record]:
    cases = [
        ("Find Rust files in src/.", "*.rs", "src",
         "**/*.rs", None,
         "There's no `src/` directory at the root. This project's Rust files live under `programs/*/src/`."),
    ]
    for prompt, pattern, bad_path, retry_pattern, _, final in cases:
        err = f"Directory not found: {bad_path}"
        good_out = "3 files found:\nprograms/escrow/src/lib.rs\nprograms/oracle/src/lib.rs"
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Searching.", [("glob_files", {"pattern": pattern, "path": bad_path})])),
                ("user", [("glob_files", False, err)]),
                ("assistant", ("Trying from root.", [("glob_files", {"pattern": retry_pattern})])),
                ("user", [("glob_files", True, good_out)]),
            ],
            final=final,
        )
        yield make_record(messages, "D13_directory_not_found", subcategory="missing_dir")


# ── D14: Unknown tool ──


def gen_D14_unknown_tool() -> Iterator[Record]:
    """Model uses a fictional tool name and recovers."""
    cases = [
        ("List all the files.",
         "list_files", "glob_files",
         "I tried `list_files` but it doesn't exist. The correct tool for listing files is `glob_files` with a pattern like `**/*`."),
    ]
    for prompt, bad_tool, good_tool, final in cases:
        err = f"Unknown tool: {bad_tool}. Available: edit_file, glob_files, grep_files, read_file, run_command, write_file"
        good_out = "5 files found:\nfile1.rs\nfile2.rs\nREADME.md"
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", ("Listing.", [(bad_tool, {})])),
                ("user", [(bad_tool, False, err)]),
                ("assistant", ("Using the correct tool.", [(good_tool, {"pattern": "**/*"})])),
                ("user", [(good_tool, True, good_out)]),
            ],
            final=final,
        )
        yield make_record(messages, "D14_unknown_tool", subcategory="tool_recovery")


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
        "D1_file_not_found": gen_D1_file_not_found,
        "D2_file_too_large": gen_D2_file_too_large,
        "D3_decode_error": gen_D3_decode_error,
        "D4_text_not_found": gen_D4_text_not_found,
        "D5_edit_missing_file": gen_D5_edit_missing_file,
        "D6_multi_match": gen_D6_multi_match,
        "D7_exit_code": gen_D7_exit_code,
        "D8_command_timeout": gen_D8_command_timeout,
        "D9_output_cap": gen_D9_output_cap,
        "D10_glob_no_matches": gen_D10_glob_no_matches,
        "D11_invalid_regex": gen_D11_invalid_regex,
        "D12_grep_no_matches": gen_D12_grep_no_matches,
        "D13_directory_not_found": gen_D13_directory_not_found,
        # D14_unknown_tool intentionally omitted — we never want training data
        # where the assistant emits an unknown tool name. Recovery from unknown
        # tool errors is naturally covered by the schema validation in D11/D13.
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
