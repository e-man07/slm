"""Group J: Tool-choice discipline (target: 600).

The Claude Code pattern: prefer dedicated tools over `run_command` shell wrappers.
Without these examples, the model defaults to `run_command(cat ...)` etc.

Subcategories:
  J1 read_file over `cat`/`head`/`tail`/`sed`         (150)
  J2 glob_files over `find -name`                     (100)
  J3 glob_files over `ls`                             (100)
  J4 grep_files over `grep`/`rg`                      (100)
  J5 edit_file over `sed -i`                          (50)
  J6 write_file over `cat > file <<EOF`               (50)
  J7 Legitimate Bash usage (anchor build, git, etc.)  (50)
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Iterator

from _tool_calling_common import build_messages, execute_tool_for_real, make_record, write_records_to_jsonl
from gen_tool_fixtures import build_fixture
from schema import Record

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "sft_tool_calling_discipline.jsonl"

PLAN_TARGET = 600

TARGETS = {
    "J1_read_over_cat": 150,
    "J2_glob_over_find": 100,
    "J3_glob_over_ls": 100,
    "J4_grep_over_grep": 100,
    "J5_edit_over_sed": 50,
    "J6_write_over_heredoc": 50,
    "J7_legitimate_bash": 50,
}


# ── J1: Use read_file instead of `cat` ──


def gen_J1_read_over_cat() -> Iterator[Record]:
    """Phrasings that COULD be solved with run_command(cat) but should use read_file."""
    cases = [
        ("Show me the contents of programs/counter/src/lib.rs.", "anchor_counter", "programs/counter/src/lib.rs"),
        ("Display Cargo.toml.", "anchor_counter", "Cargo.toml"),
        ("What's in programs/escrow/src/lib.rs?", "multi_workspace", "programs/escrow/src/lib.rs"),
        ("Print the README.", "anchor_counter", "README.md"),
        ("View Anchor.toml.", "anchor_counter", "Anchor.toml"),
        ("Open programs/oracle/src/lib.rs.", "multi_workspace", "programs/oracle/src/lib.rs"),
        ("Cat the package.json.", "anchor_counter", "package.json"),
        ("Show the test file.", "anchor_counter", "tests/counter.ts"),
    ]
    for prompt, fixture, path in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("read_file", {"path": path}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Reading the file.", [("read_file", {"path": path})])),
                    ("user", [("read_file", True, r.output)]),
                ],
                final=f"Contents of `{path}` shown above.",
            )
            yield make_record(messages, "J1_read_over_cat", subcategory=fixture)


# ── J2: Use glob_files instead of `find -name` ──


def gen_J2_glob_over_find() -> Iterator[Record]:
    cases = [
        ("Find all .rs files in this project.", "anchor_counter", "**/*.rs"),
        ("Locate every TOML file.", "multi_workspace", "**/*.toml"),
        ("Where are all the .ts files?", "anchor_counter", "**/*.ts"),
        ("Find all Cargo.toml files.", "multi_workspace", "**/Cargo.toml"),
        ("Search for lib.rs files.", "multi_workspace", "**/lib.rs"),
    ]
    for prompt, fixture, pattern in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("glob_files", {"pattern": pattern}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Searching with glob_files.", [("glob_files", {"pattern": pattern})])),
                    ("user", [("glob_files", True, r.output)]),
                ],
                final=f"Found the matching files above.",
            )
            yield make_record(messages, "J2_glob_over_find", subcategory=pattern)


# ── J3: glob_files over `ls` ──


def gen_J3_glob_over_ls() -> Iterator[Record]:
    cases = [
        ("List the files in programs/counter/src/.", "anchor_counter", "*", "programs/counter/src"),
        ("Show me what's in tests/.", "anchor_counter", "*", "tests"),
        ("What's in the programs directory?", "multi_workspace", "*", "programs"),
        ("List files at the project root.", "anchor_counter", "*", "."),
    ]
    for prompt, fixture, pattern, path in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("glob_files", {"pattern": pattern, "path": path}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", (f"Listing `{path}`.", [("glob_files", {"pattern": pattern, "path": path})])),
                    ("user", [("glob_files", True, r.output)]),
                ],
                final=f"Files in `{path}` listed above.",
            )
            yield make_record(messages, "J3_glob_over_ls", subcategory=fixture)


# ── J4: grep_files over `grep`/`rg` ──


def gen_J4_grep_over_grep() -> Iterator[Record]:
    cases = [
        ("Search the codebase for `declare_id!`.", "anchor_legacy", "declare_id!"),
        ("Find every place we use `Pubkey`.", "multi_workspace", "Pubkey"),
        ("Grep for `#[program]`.", "multi_workspace", "#\\[program\\]"),
        ("Where is `ctx.bumps` referenced?", "anchor_counter", "ctx\\.bumps"),
        ("Look for `Result<()>` in the source.", "anchor_counter", "Result<\\(\\)>"),
    ]
    for prompt, fixture, pattern in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Searching with grep_files.", [("grep_files", {"pattern": pattern})])),
                    ("user", [("grep_files", True, r.output)]),
                ],
                final="Search complete.",
            )
            yield make_record(messages, "J4_grep_over_grep", subcategory=fixture)


# ── J5: edit_file over `sed -i` ──


def gen_J5_edit_over_sed() -> Iterator[Record]:
    cases = [
        ("Replace `count = 0` with `count = 1` in programs/counter/src/lib.rs.",
         "anchor_counter", "programs/counter/src/lib.rs",
         "ctx.accounts.counter.count = 0;", "ctx.accounts.counter.count = 1;",
         "Replaced via `edit_file` (which I prefer over `sed -i` because it's safer — exact-text match, "
         "no regex pitfalls, no risk of partial replacement)."),
    ]
    for prompt, fixture, rel_path, old_t, new_t, final in cases:
        with build_fixture(fixture) as fx:
            r = execute_tool_for_real("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t}, fx.path)
            if not r.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Using edit_file for safe replacement.", [("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t})])),
                    ("user", [("edit_file", True, r.output)]),
                ],
                final=final,
            )
            yield make_record(messages, "J5_edit_over_sed", subcategory=fixture)


# ── J6: write_file over `cat > file <<EOF` ──


def gen_J6_write_over_heredoc() -> Iterator[Record]:
    cases = [
        ("Create a `.gitignore` for this Rust project.",
         ".gitignore", "target/\nnode_modules/\n.anchor/\n",
         "Created `.gitignore` with the standard entries (using `write_file` rather than a shell heredoc — cleaner)."),
        ("Add a `version.txt` file with `0.1.0`.",
         "version.txt", "0.1.0\n",
         "Wrote the version file."),
        ("Write a CHANGELOG.md template.",
         "CHANGELOG.md", "# Changelog\n\n## [0.1.0]\n- Initial release\n",
         "CHANGELOG template created."),
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
        yield make_record(messages, "J6_write_over_heredoc", subcategory=path)


# ── J7: Legitimate Bash usage ──


def gen_J7_legitimate_bash() -> Iterator[Record]:
    """Cases where run_command IS the right tool — anchor/cargo/git operations."""
    cases = [
        ("Build the program.", "anchor build",
         "Compiling counter v0.1.0\nFinished `release` profile in 12.4s",
         "Build succeeded. `run_command` is the right tool here — `anchor build` is a shell operation that "
         "compiles to BPF; no dedicated tool exists."),
        ("Run the test suite.", "anchor test",
         "  counter\n    ✓ initializes (245ms)\n  1 passing",
         "Tests pass. `run_command` is correct here — test execution is inherently a subprocess operation."),
        ("Check git status.", "git status",
         "On branch main\nnothing to commit, working tree clean",
         "Working tree clean."),
        ("What version of solana CLI is installed?", "solana --version",
         "solana-cli 1.18.1",
         "Solana CLI 1.18.1."),
        ("Run cargo fmt across the workspace.", "cargo fmt",
         "(no output)",
         "Formatting applied."),
        ("Initialize a new git repository.", "git init",
         "Initialized empty Git repository in /tmp/myproj/.git/",
         "Git repository initialized."),
    ]
    for prompt, cmd, output, final in cases:
        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Running `{cmd}`.", [("run_command", {"command": cmd})])),
                ("user", [("run_command", True, output)]),
            ],
            final=final,
        )
        yield make_record(messages, "J7_legitimate_bash", subcategory=cmd.split()[0])


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
        "J1_read_over_cat": gen_J1_read_over_cat,
        "J2_glob_over_find": gen_J2_glob_over_find,
        "J3_glob_over_ls": gen_J3_glob_over_ls,
        "J4_grep_over_grep": gen_J4_grep_over_grep,
        "J5_edit_over_sed": gen_J5_edit_over_sed,
        "J6_write_over_heredoc": gen_J6_write_over_heredoc,
        "J7_legitimate_bash": gen_J7_legitimate_bash,
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
