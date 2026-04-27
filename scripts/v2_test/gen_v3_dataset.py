"""V3 targeted dataset — fix the v2 failure modes seen in agent test.

Test results that motivated this:
  single_grep:  0/5 (0%)   — model fakes grep results instead of calling grep_files
  tool_choice:  1/4 (25%)  — model lapses into prose for "show me X" prompts
  single_read:  4/6 (67%)  — fails on conversational ("show me", "display") phrasings
  single_write: 2/4 (50%)  — fails on indirect write requests
  single_edit:  2/3 (67%)  — fails on rename without exact text

This generator emits ~5K examples concentrated on those failure modes:

  V3-A: grep_files emphasis        2000 records
  V3-B: tool-choice discipline     1200 records (extends Group J pattern)
  V3-C: conversational reads       800  records ("show me", "display", "view")
  V3-D: explicit "use tool X" phrasings  500 records
  V3-E: edit_file diversity        500 records

  Total: 5,000 examples
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

# Reuse common helpers + fixtures from main scripts dir
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

OUTPUT_PATH = Path(__file__).resolve().parent / "sft_v3_targeted.jsonl"


# ── V3-A: Heavy grep_files emphasis (2000 target) ──
# Model learned to FAKE grep output. Counter with examples that show the
# canonical pattern: emit tool_call → user provides tool_result → assistant summarizes.

def gen_grep_emphasis():
    rng = random.Random(301)
    # Many real searches across all fixtures
    grep_targets = [
        ("anchor_counter", "#\\[program\\]"),
        ("anchor_counter", "ctx\\.bumps"),
        ("anchor_counter", "Result<\\(\\)>"),
        ("anchor_counter", "pub fn"),
        ("anchor_counter", "#\\[account\\]"),
        ("anchor_counter", "Pubkey"),
        ("anchor_counter", "Signer"),
        ("anchor_counter", "init"),
        ("anchor_counter", "seeds"),
        ("anchor_counter", "bump"),
        ("anchor_vault", "use anchor_spl"),
        ("anchor_vault", "Transfer"),
        ("anchor_vault", "transfer"),
        ("anchor_vault", "TokenAccount"),
        ("anchor_vault", "CpiContext"),
        ("anchor_vault", "#\\[error_code\\]"),
        ("anchor_buggy", "ctx\\.bumps\\.get"),
        ("anchor_buggy", "unwrap"),
        ("anchor_legacy", "declare_id!"),
        ("anchor_legacy", "ProgramResult"),
        ("multi_workspace", "#\\[program\\]"),
        ("multi_workspace", "Pubkey"),
        ("multi_workspace", "Signer"),
        ("multi_workspace", "Account"),
        ("multi_workspace", "has_one"),
        ("multi_workspace", "init"),
        ("native_solana", "entrypoint!"),
        ("native_solana", "process_instruction"),
        ("native_solana", "AccountInfo"),
        ("pinocchio", "pinocchio"),
        ("pinocchio", "AccountInfo"),
    ]

    phrasings = [
        "Search for `{p}` in {fx}.",
        "Find all references to `{p}` in {fx}.",
        "Where is `{p}` used in {fx}?",
        "Look for `{p}` across {fx}.",
        "Grep `{p}` in {fx}.",
        "Find `{p}` in {fx}.",
        "Show me where `{p}` is used in {fx}.",
        "Locate `{p}` references in {fx}.",
        "Hunt for `{p}` in {fx}.",
        "Scan {fx} for `{p}`.",
        "Tell me where `{p}` appears in {fx}.",
        "Find every place `{p}` shows up in {fx}.",
        "Search the {fx} codebase for `{p}`.",
        "Find usages of `{p}` in {fx}.",
        "Locate every instance of `{p}` in {fx}.",
    ]

    for fixture_name, pattern in grep_targets:
        with build_fixture(fixture_name) as fx:
            result = execute_tool_for_real("grep_files", {"pattern": pattern}, fx.path)
            if not result.success:
                continue

            friendly = pattern.replace("\\", "")
            # Generate multiple phrasings per (fixture, pattern) pair
            for phrasing in phrasings:
                user_msg = phrasing.format(p=friendly, fx=fixture_name)

                # Build summary based on result
                if "No matches" in result.output:
                    final = f"No matches for `{friendly}` in {fixture_name}."
                else:
                    line_count = result.output.count("\n") + 1
                    final = (
                        f"Found `{friendly}` in {fixture_name}. "
                        f"There are {line_count} match(es) — see the output above for the file:line:content list."
                    )

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Searching the codebase.", [("grep_files", {"pattern": pattern})])),
                        ("user", [("grep_files", True, result.output)]),
                    ],
                    final=final,
                )
                yield make_record(messages, "V3A_grep_emphasis", subcategory=fixture_name)


# ── V3-B: Tool-choice discipline (1200 target) ──
# Strengthen "show me X" → read_file (NOT run_command(cat))
# "find" → glob_files, "search" → grep_files, "list" → glob_files

def gen_discipline_v3():
    rng = random.Random(302)

    read_phrasings = [
        "Show me the contents of {path}.",
        "What's in {path}?",
        "Display {path}.",
        "Open {path} for me.",
        "View {path}.",
        "I want to see {path}.",
        "Print {path}.",
        "Let me see {path}.",
        "Show {path}'s content.",
        "Pull up {path}.",
        "Bring up {path}.",
        "What does {path} contain?",
        "Read {path}.",
        "Look at {path}.",
        "Cat {path}.",
        "Could you show me {path}?",
    ]

    glob_phrasings = [
        "List the files in {path}.",
        "Find all {pat} files in {path}.",
        "What files are in {path}?",
        "Show me the files under {path}.",
        "Locate {pat} files in {path}.",
        "ls {path}",
        "What's inside {path}?",
        "Browse {path}.",
        "Show contents of directory {path}.",
    ]

    grep_phrasings = [
        "Search for `{pat}` in {path}.",
        "Find `{pat}` in {path}.",
        "Where is `{pat}` in {path}?",
        "Look for `{pat}` in {path}.",
        "Grep for `{pat}` in {path}.",
        "Find all matches of `{pat}` in {path}.",
        "Hunt for `{pat}` in {path}.",
    ]

    # ── J1: read_file over cat ──
    file_targets = [
        ("anchor_counter", "Anchor.toml"),
        ("anchor_counter", "Cargo.toml"),
        ("anchor_counter", "programs/counter/src/lib.rs"),
        ("anchor_counter", "tests/counter.ts"),
        ("anchor_counter", "package.json"),
        ("anchor_counter", "README.md"),
        ("anchor_vault", "programs/vault/src/lib.rs"),
        ("anchor_vault", "programs/vault/Cargo.toml"),
        ("multi_workspace", "Anchor.toml"),
        ("multi_workspace", "programs/escrow/src/lib.rs"),
        ("multi_workspace", "programs/oracle/src/lib.rs"),
    ]
    for fixture_name, rel_path in file_targets:
        with build_fixture(fixture_name) as fx:
            result = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            if not result.success:
                continue
            for phrasing in read_phrasings:
                user_msg = phrasing.format(path=rel_path)
                final = f"Showing contents of `{rel_path}`."
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Reading the file.", [("read_file", {"path": rel_path})])),
                        ("user", [("read_file", True, result.output)]),
                    ],
                    final=final,
                )
                yield make_record(messages, "V3B_discipline_read", subcategory=fixture_name)

    # ── J2/J3: glob over find/ls ──
    glob_targets = [
        ("anchor_counter", "*.rs", "."),
        ("anchor_counter", "**/*.rs", "."),
        ("anchor_counter", "*.toml", "."),
        ("multi_workspace", "**/*.rs", "programs"),
        ("multi_workspace", "**/Cargo.toml", "."),
        ("multi_workspace", "*", "programs"),
        ("anchor_vault", "**/*.rs", "."),
    ]
    for fixture_name, pattern, search_path in glob_targets:
        with build_fixture(fixture_name) as fx:
            result = execute_tool_for_real("glob_files", {"pattern": pattern, "path": search_path}, fx.path)
            if not result.success:
                continue
            for phrasing in glob_phrasings:
                user_msg = phrasing.format(pat=pattern, path=search_path)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Searching with glob_files.", [("glob_files", {"pattern": pattern, "path": search_path})])),
                        ("user", [("glob_files", True, result.output)]),
                    ],
                    final="Files listed above.",
                )
                yield make_record(messages, "V3B_discipline_glob", subcategory=fixture_name)


# ── V3-C: Conversational reads (already covered above in V3-B's read_phrasings, but add a few more contexts) ──

def gen_conversational_reads():
    """More variety: implicit asks like 'I want to understand X'."""
    rng = random.Random(303)
    targets = [
        ("anchor_counter", "programs/counter/src/lib.rs",
         ["I want to understand the counter program — show me the code.",
          "Help me figure out how this counter works. Read the lib.rs.",
          "Walk me through the counter program by reading its source.",
          "I need to look at the counter implementation.",
          "Pull up the counter's main file."]),
        ("anchor_vault", "programs/vault/src/lib.rs",
         ["What does the vault program look like?",
          "Show me the vault's source code.",
          "I'd like to see how the vault is implemented."]),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         ["I want to read the escrow program.",
          "Show me how the escrow is implemented.",
          "Pull up the escrow's lib.rs."]),
    ]
    for fixture_name, rel_path, prompts in targets:
        with build_fixture(fixture_name) as fx:
            result = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            if not result.success:
                continue
            for prompt in prompts:
                messages = build_messages(
                    user_msg=prompt,
                    trajectory=[
                        ("assistant", ("Reading the file.", [("read_file", {"path": rel_path})])),
                        ("user", [("read_file", True, result.output)]),
                    ],
                    final=f"Source of `{rel_path}` shown above.",
                )
                yield make_record(messages, "V3C_conversational_read", subcategory=fixture_name)


# ── V3-D: Explicit "use tool X" prompts (defensive examples) ──
# Teach the model that when user explicitly names a tool, it MUST call that tool.

def gen_explicit_tool_naming():
    rng = random.Random(304)
    cases = [
        ("Use the read_file tool to read /tmp/foo.rs",
         "read_file", {"path": "/tmp/foo.rs"},
         "File read.", "/tmp/foo.rs"),
        ("Run grep_files to find `Pubkey` in the codebase",
         "grep_files", {"pattern": "Pubkey"},
         "Search done.", None),
        ("Call glob_files with pattern '**/*.rs'",
         "glob_files", {"pattern": "**/*.rs"},
         "Files listed.", None),
        ("Use read_file on Anchor.toml",
         "read_file", {"path": "Anchor.toml"},
         "Anchor.toml shown.", None),
        ("Explicitly invoke grep_files for `declare_id`",
         "grep_files", {"pattern": "declare_id"},
         "Searched for declare_id.", None),
    ]
    for prompt, tool_name, args, final, _ in cases:
        # Synthesize a generic result
        if tool_name == "read_file":
            result_str = f"File: {args.get('path', '?')} (10 lines, showing 1-10)\n   1 | // example content"
        elif tool_name == "grep_files":
            result_str = f"src/lib.rs:5: matched line containing {args.get('pattern')}"
        elif tool_name == "glob_files":
            result_str = "3 files found:\nlib.rs\nstate.rs\nerror.rs"
        else:
            result_str = "(no output)"

        messages = build_messages(
            user_msg=prompt,
            trajectory=[
                ("assistant", (f"Calling {tool_name}.", [(tool_name, args)])),
                ("user", [(tool_name, True, result_str)]),
            ],
            final=final,
        )
        yield make_record(messages, "V3D_explicit_tool", subcategory=tool_name)


# ── V3-E: edit_file diversity ──

def gen_edit_diversity():
    cases = [
        ("anchor_counter", "programs/counter/src/lib.rs",
         "ctx.accounts.counter.count = 0;", "ctx.accounts.counter.count = 0u64;",
         "Make the initial count explicit u64."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         '*ctx.bumps.get("profile").unwrap()', "ctx.bumps.profile",
         "Replace the deprecated bump access pattern with the modern field-access form."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "ProgramResult", "Result<()>",
         "Update to modern Anchor return type."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         'declare_id!("Fg6PaFpoGXkKXx2KcD684s5rJNHHk3JG462ZiJxkZuFZ");',
         "// Program ID is set in Anchor.toml",
         "Remove the deprecated declare_id! macro."),
    ]
    for fixture_name, rel_path, old_t, new_t, prompt in cases:
        with build_fixture(fixture_name) as fx:
            result = execute_tool_for_real("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t}, fx.path)
            if not result.success:
                continue
            messages = build_messages(
                user_msg=prompt,
                trajectory=[
                    ("assistant", ("Editing the file.", [("edit_file", {"path": rel_path, "old_text": old_t, "new_text": new_t})])),
                    ("user", [("edit_file", True, result.output)]),
                ],
                final=f"Edited `{rel_path}`.",
            )
            yield make_record(messages, "V3E_edit_diversity", subcategory=fixture_name)


# ── Main ──

def expand_to_target(records, target, seed=42):
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


def main():
    targets = {
        "V3A_grep": (gen_grep_emphasis, 2000),
        "V3B_discipline": (gen_discipline_v3, 1200),
        "V3C_conversational": (gen_conversational_reads, 800),
        "V3D_explicit": (gen_explicit_tool_naming, 500),
        "V3E_edit": (gen_edit_diversity, 500),
    }

    all_records = []
    for name, (gen_fn, target) in targets.items():
        raw = list(gen_fn())
        scaled = expand_to_target(raw, target, seed=hash(name) & 0xFFFF)
        print(f"  {name}: {len(raw)} unique → {len(scaled)} records (target {target})")
        all_records.extend(scaled)

    print(f"\nTotal V3 records: {len(all_records)}")
    write_records_to_jsonl(all_records, OUTPUT_PATH)


if __name__ == "__main__":
    main()
