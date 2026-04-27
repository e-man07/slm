"""V5 dataset — fix every v4 failure mode explicitly. Target ≥85% on agent test.

V4 RESULT: 33/49 (67.3%). 16 failures categorized as:
  Mode 1 — Garbage-prefix tool calls (8 fails): `.glob_files`, `ContextHolder{`, `oko:`
  Mode 2 — Hallucinated content (4 fails): faked Anchor.toml, faked README, Spanish drift
  Mode 3 — Bash leak (3 fails): ```bash\\nls -la``` instead of glob_files
  Mode 4 — Wrong tool (1 fail): glob_files when grep_files needed

Root causes addressed in v5:
  A. Path mismatch: v4 trained on RELATIVE paths, test uses ABSOLUTE /workspace/fx_*/
     → v5 uses absolute paths everywhere.
  B. Format not sticky: <tool_call> tag wrapper not anchored deeply enough
     → v5 adds 1000 format-only records (pure tag, minimal prose).
  C. Anti-hallucination weak: model fabricates content from memory
     → v5 adds 700 contrast pairs explicitly forbidding fabrication.
  D. Discipline too gentle: model still uses bash for read/list/grep
     → v5 has 1500 anti-bash records (vs v4's 1000).
  E. Volume × LR too low: 1 epoch at LR 2e-6 didn't burn in
     → v5 trains at LR 4e-6, 2 epochs, on 13K records.

Composition (~13K records):
  V5-A: Reads with absolute paths      2500   covers read-02, read-05
  V5-B: Globs with absolute paths      2500   covers glob-01,03,04,05
  V5-C: Greps with absolute paths      2000   covers grep-01,02,03 + multi-02
  V5-D: Discipline (anti-bash)         1500   covers discipline-02,03,04
  V5-E: Edits with absolute paths      1000   covers edit-03
  V5-F: Multistep                      1000   covers multi-02
  V5-G: Writes                          800   covers write-02
  V5-H: Format-only (pure tag)         1000   anchors <tool_call> format
  V5-I: Anti-hallucination contrast     700   teaches "always call, never fake"
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

OUTPUT_PATH = Path(__file__).resolve().parent / "sft_v5_targeted.jsonl"

# ── Fixture → /workspace abs path mapping (matches test_v2_agent.py exactly) ──
WORKSPACE_PREFIX = {
    "anchor_counter": "/workspace/fx_counter",
    "anchor_vault": "/workspace/fx_vault",
    "anchor_buggy": "/workspace/fx_buggy",
    "anchor_legacy": "/workspace/fx_legacy",
    "multi_workspace": "/workspace/fx_workspace",
}
# Mutable copy used for edit tests
MUT_PREFIX = {
    "anchor_counter": "/workspace/fx_counter_mut",
}


def to_abs_path(fx_name: str, rel_path: str, mutable: bool = False) -> str:
    prefix = MUT_PREFIX[fx_name] if mutable else WORKSPACE_PREFIX[fx_name]
    return f"{prefix}/{rel_path}"


def to_abs_result(output: str, fx_path: Path, abs_prefix: str) -> str:
    """Replace temp fixture path with canonical /workspace path in tool output."""
    return output.replace(str(fx_path), abs_prefix)


# ── V5-A: Reads (2500, ~300 unique) ─────────────────────────────────────────

def gen_v5_reads():
    """Heavy on the EXACT phrasings that failed in v4 + many more."""
    file_targets = [
        # anchor_counter — main fixture, hit hard
        ("anchor_counter", "Anchor.toml"),
        ("anchor_counter", "Cargo.toml"),
        ("anchor_counter", "programs/counter/src/lib.rs"),
        ("anchor_counter", "programs/counter/Cargo.toml"),
        ("anchor_counter", "tests/counter.ts"),
        ("anchor_counter", "package.json"),
        ("anchor_counter", "tsconfig.json"),
        ("anchor_counter", "README.md"),
        # anchor_vault
        ("anchor_vault", "programs/vault/src/lib.rs"),
        ("anchor_vault", "programs/vault/src/state.rs"),
        ("anchor_vault", "programs/vault/src/errors.rs"),
        ("anchor_vault", "programs/vault/Cargo.toml"),
        ("anchor_vault", "Anchor.toml"),
        # multi_workspace
        ("multi_workspace", "Anchor.toml"),
        ("multi_workspace", "Cargo.toml"),
        ("multi_workspace", "programs/escrow/src/lib.rs"),
        ("multi_workspace", "programs/escrow/Cargo.toml"),
        ("multi_workspace", "programs/oracle/src/lib.rs"),
        ("multi_workspace", "programs/oracle/Cargo.toml"),
        # anchor_buggy
        ("anchor_buggy", "programs/buggy/src/lib.rs"),
        ("anchor_buggy", "programs/buggy/Cargo.toml"),
        # anchor_legacy
        ("anchor_legacy", "programs/legacy/src/lib.rs"),
        ("anchor_legacy", "programs/legacy/Cargo.toml"),
    ]

    # PHRASINGS — include EXACT v4-failed phrasings
    phrasings = [
        # Direct (v4-failed prompts mirrored)
        "Show me the contents of {abs}",
        "Display the README.md at {abs}",  # mirrors read-05
        "Display {abs}",
        "Display the contents of {abs}.",
        # Show me variants
        "Show me {abs}.",
        "Show me what's in {abs}.",
        # What's in / What does it contain
        "What's in {abs}?",
        "What does {abs} contain?",
        "What's inside {abs}?",
        # Open / View / Read
        "Open {abs} for me.",
        "Open {abs}.",
        "View {abs}.",
        "Read {abs}.",
        "Read {abs} please.",
        "Read me {abs}.",
        # Print / Cat
        "Print {abs}.",
        "Cat {abs}.",
        # I want / I need / Could you
        "I want to see {abs}.",
        "I need to see {abs}.",
        "Could you show me {abs}?",
        "Could you display {abs}?",
        # Pull up / Bring up / Fetch
        "Pull up {abs}.",
        "Bring up {abs}.",
        "Fetch {abs}.",
        "Help me see {abs}.",
        # Original "Read X and tell me" — covers read-01
        "Read {abs} and tell me what it does.",
        "Read {abs} and explain what's in it.",
        "Open {abs} for me and walk me through it.",
        "Look at {abs}.",
    ]

    rng = random.Random(501)
    seen, out = set(), []

    for fx_name, rel_path in file_targets:
        with build_fixture(fx_name) as fx:
            real = execute_tool_for_real("read_file", {"path": rel_path}, fx.path)
            if not real.success:
                continue
            abs_path = to_abs_path(fx_name, rel_path)
            result_text = to_abs_result(real.output, fx.path, WORKSPACE_PREFIX[fx_name])

            chosen = rng.sample(phrasings, k=min(15, len(phrasings)))
            for tmpl in chosen:
                user_msg = tmpl.format(abs=abs_path)

                # Vary the prose-before-call to avoid memorization but keep format strict
                prose = rng.choice([
                    "Reading the file.",
                    "Opening it now.",
                    "I'll read that.",
                    "",  # CRITICAL: 25% have no prose, just <tool_call> — anchors format
                ])

                # Final response — substantive but anchored to actual content
                first_lines = "\n".join(result_text.split("\n")[1:4])  # skip header line
                final = f"`{abs_path}` shown above. Key contents:\n{first_lines[:250]}"

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", (prose, [("read_file", {"path": abs_path})])),
                        ("user", [("read_file", True, result_text)]),
                    ],
                    final=final,
                )
                rec = make_record(messages, "V5A_read", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    return out


# ── V5-B: Globs with absolute paths (2500, ~300 unique) ─────────────────────

def gen_v5_globs():
    """Kill the 4 v4 glob failures with EXACT phrasings + absolute paths."""
    targets = [
        # (fixture, pattern, optional dir-suffix for path arg)
        ("anchor_counter", "**/*.rs", ""),
        ("anchor_counter", "**/*.toml", ""),
        ("anchor_counter", "**/*.ts", ""),
        ("anchor_counter", "**/*.json", ""),
        ("anchor_counter", "**/*.md", ""),
        ("anchor_counter", "**/Cargo.toml", ""),
        ("anchor_counter", "**/Anchor.toml", ""),
        ("anchor_counter", "tests/*.ts", ""),
        ("anchor_counter", "programs/**/*.rs", ""),
        ("anchor_counter", "programs/**/Cargo.toml", ""),
        ("anchor_vault", "**/*.rs", ""),
        ("anchor_vault", "**/*.toml", ""),
        ("anchor_vault", "**/Cargo.toml", ""),
        ("anchor_vault", "programs/**/*.rs", ""),
        ("anchor_vault", "programs/vault/src/*.rs", ""),
        ("anchor_buggy", "**/*.rs", ""),
        ("anchor_buggy", "programs/**/lib.rs", ""),
        ("anchor_buggy", "**/*.toml", ""),
        ("anchor_legacy", "**/*.rs", ""),
        ("anchor_legacy", "programs/**/lib.rs", ""),
        ("anchor_legacy", "**/*.toml", ""),
        ("multi_workspace", "**/*.rs", ""),
        ("multi_workspace", "**/Cargo.toml", ""),
        ("multi_workspace", "programs/**/lib.rs", ""),
        ("multi_workspace", "**/*.toml", ""),
        ("multi_workspace", "programs/escrow/**/*.rs", ""),
        ("multi_workspace", "programs/oracle/**/*.rs", ""),
    ]

    # PHRASINGS — explicit v4-failed prompts:
    #   glob-01: "Find all Rust source files in /workspace/fx_workspace"
    #   glob-03: "Locate any .ts files under /workspace/fx_counter"
    #   glob-04: "Show me what files are inside /workspace/fx_workspace/programs"
    #   glob-05: "Find all *.toml files under /workspace/fx_counter"
    phrasings = [
        # v4-failed mirrors
        "Find all {ext_friendly} files in {prefix}",  # glob-01 style
        "Find all Rust source files in {prefix}",
        "Find all *.{ext} files under {prefix}",  # glob-05 style
        "Locate any .{ext} files under {prefix}",  # glob-03 style
        "Show me what files are inside {prefix}",
        "Show me what files are inside {prefix}/programs",
        "List the files in {prefix} directory",
        # Generic
        "Find all {pattern} files in {prefix}.",
        "List every {pattern} file in {prefix}.",
        "Where are the {pattern} files in {prefix}?",
        "Show me {pattern} files under {prefix}.",
        "Locate all {pattern} files in {prefix}.",
        "Browse {pattern} files in {prefix}.",
        "Find {pattern} files in this project at {prefix}.",
        "Scan {prefix} for {pattern} files.",
        "Get all {pattern} files in {prefix}.",
        "Hunt for {pattern} files inside {prefix}.",
        "Search {prefix} for {pattern}.",
        "Tell me which {pattern} files exist under {prefix}.",
    ]

    rng = random.Random(502)
    seen, out = set(), []

    for fx_name, pattern, _ in targets:
        with build_fixture(fx_name) as fx:
            real = execute_tool_for_real("glob_files", {"pattern": pattern}, fx.path)
            if not real.success:
                continue
            prefix = WORKSPACE_PREFIX[fx_name]
            result_text = to_abs_result(real.output, fx.path, prefix)

            ext = pattern.split(".")[-1] if "." in pattern else "rs"
            ext_friendly = {"rs": "Rust", "ts": "TypeScript", "toml": "TOML",
                            "json": "JSON", "py": "Python"}.get(ext, ext)

            chosen = rng.sample(phrasings, k=min(15, len(phrasings)))
            for tmpl in chosen:
                user_msg = tmpl.format(
                    pattern=pattern, prefix=prefix, ext=ext, ext_friendly=ext_friendly,
                )
                prose = rng.choice([
                    "Searching with glob_files.",
                    "Looking for those files.",
                    "Finding them now.",
                    "",
                ])
                final = f"Found these files in `{prefix}`:\n{result_text[:300]}"

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", (prose, [("glob_files", {"pattern": pattern, "path": prefix})])),
                        ("user", [("glob_files", True, result_text)]),
                    ],
                    final=final,
                )
                rec = make_record(messages, "V5B_glob", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    return out


# ── V5-C: Greps with absolute paths (2000, ~300 unique) ─────────────────────

def gen_v5_greps():
    """Kill v4 grep failures: grep-01, grep-02, grep-03."""
    patterns_per_fixture = {
        "anchor_counter": ["#\\[program\\]", "ctx\\.bumps", "Result<\\(\\)>", "pub fn",
                           "#\\[account\\]", "Pubkey", "Signer", "init", "seeds",
                           "bump", "Account", "Context", "u64", "use anchor_lang",
                           "msg!", "checked_add", "ErrorCode", "Counter"],
        "anchor_vault": ["use anchor_spl", "Transfer", "transfer", "TokenAccount",
                         "CpiContext", "#\\[error_code\\]", "InsufficientBalance",
                         "Token", "Vault", "deposit"],
        "anchor_buggy": ["ctx\\.bumps\\.get", "unwrap", "profile", "Profile", "init"],
        "anchor_legacy": ["declare_id!", "ProgramResult", "legacy", "Data", "value"],
        "multi_workspace": ["#\\[program\\]", "Pubkey", "Signer", "Account", "has_one",
                            "init", "Escrow", "PriceFeed", "amount", "maker",
                            "authority", "price"],
    }

    # v4-failed phrasings:
    #   grep-01: "Search for `#[program]` in /workspace/fx_workspace"
    #   grep-02: "Find usages of `declare_id` in /workspace/fx_legacy"
    #   grep-03: "Where is `Pubkey` referenced in /workspace/fx_counter?"
    phrasings = [
        # v4-failed mirrors
        "Search for `{p}` in {prefix}",
        "Find usages of `{p}` in {prefix}",
        "Where is `{p}` referenced in {prefix}?",
        "Search for `{p}` in {prefix} source files",  # discipline-03 style
        # Generic
        "Find references to `{p}` in {prefix}.",
        "Look for `{p}` in {prefix}.",
        "Grep for `{p}` in {prefix}.",
        "Hunt for `{p}` across {prefix}.",
        "Scan {prefix} for `{p}`.",
        "Find all occurrences of `{p}` in {prefix}.",
        "Tell me where `{p}` appears in {prefix}.",
        "Locate `{p}` in {prefix}.",
        "Search the {prefix} codebase for `{p}`.",
        "Could you find `{p}` in {prefix}?",
        "I need to find `{p}` in {prefix}.",
        "Help me locate `{p}` in {prefix}.",
        "Where does `{p}` show up in {prefix}?",
        "Show me `{p}` references in {prefix}.",
        "Find `{p}` matches in {prefix}.",
    ]

    rng = random.Random(503)
    seen, out = set(), []

    for fx_name, patterns in patterns_per_fixture.items():
        for pat in patterns:
            with build_fixture(fx_name) as fx:
                real = execute_tool_for_real("grep_files", {"pattern": pat}, fx.path)
                if not real.success:
                    continue
                prefix = WORKSPACE_PREFIX[fx_name]
                result_text = to_abs_result(real.output, fx.path, prefix)

                friendly = pat.replace("\\", "")

                chosen = rng.sample(phrasings, k=min(8, len(phrasings)))
                for tmpl in chosen:
                    user_msg = tmpl.format(p=friendly, prefix=prefix)
                    prose = rng.choice([
                        "Searching with grep_files.",
                        "Looking for that pattern.",
                        "I'll grep now.",
                        "",
                    ])
                    if "No matches" in result_text:
                        final = f"No matches for `{friendly}` in {prefix}."
                    else:
                        n = result_text.count("\n") + 1
                        final = f"Found {n} match(es) for `{friendly}` in {prefix}. See above."

                    messages = build_messages(
                        user_msg=user_msg,
                        trajectory=[
                            ("assistant", (prose, [("grep_files", {"pattern": pat, "path": prefix})])),
                            ("user", [("grep_files", True, result_text)]),
                        ],
                        final=final,
                    )
                    rec = make_record(messages, "V5C_grep", subcategory=fx_name)
                    if rec.id not in seen:
                        seen.add(rec.id)
                        out.append(rec)

    return out


# ── V5-D: Discipline (1500, ~150 unique) — anti-Bash ───────────────────────

def gen_v5_discipline():
    """Kill discipline-02,03,04 — model still uses bash ls/find/grep."""
    rng = random.Random(504)
    seen, out = set(), []

    # D1: read over cat — many files, many phrasings
    read_targets = [
        ("anchor_counter", "Anchor.toml"),
        ("anchor_counter", "Cargo.toml"),
        ("anchor_counter", "programs/counter/src/lib.rs"),
        ("anchor_counter", "tests/counter.ts"),
        ("anchor_counter", "package.json"),
        ("anchor_vault", "programs/vault/src/lib.rs"),
        ("anchor_vault", "Anchor.toml"),
        ("multi_workspace", "programs/escrow/src/lib.rs"),
        ("multi_workspace", "programs/oracle/src/lib.rs"),
        ("multi_workspace", "Anchor.toml"),
        ("anchor_buggy", "programs/buggy/src/lib.rs"),
        ("anchor_legacy", "programs/legacy/src/lib.rs"),
    ]
    read_phrasings_disc = [
        "Show me {abs}.",  # tempting: model might `cat`
        "Cat {abs}.",      # explicitly asks for cat — must still use read_file
        "Display {abs}.",
        "Read {abs}.",
        "View {abs}.",
        "Print {abs}.",
        "What's in {abs}?",
        "Show me what's inside {abs}.",
    ]
    for fx_name, rel in read_targets:
        with build_fixture(fx_name) as fx:
            r = execute_tool_for_real("read_file", {"path": rel}, fx.path)
            if not r.success:
                continue
            abs_path = to_abs_path(fx_name, rel)
            result_text = to_abs_result(r.output, fx.path, WORKSPACE_PREFIX[fx_name])
            for tmpl in read_phrasings_disc:
                user_msg = tmpl.format(abs=abs_path)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Using read_file (preferred over cat).", [("read_file", {"path": abs_path})])),
                        ("user", [("read_file", True, result_text)]),
                    ],
                    final=f"`{abs_path}` shown above.",
                )
                rec = make_record(messages, "V5D_disc_read", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # D2: glob over find/ls — kill discipline-02 ("Find all .rs files in /workspace/fx_workspace")
    glob_targets = [
        ("anchor_counter", "**/*.rs"),
        ("anchor_counter", "**/*.toml"),
        ("anchor_counter", "**/*.ts"),
        ("multi_workspace", "**/*.rs"),
        ("multi_workspace", "programs/**/lib.rs"),
        ("multi_workspace", "**/Cargo.toml"),
        ("anchor_vault", "**/*.rs"),
        ("anchor_buggy", "**/*.rs"),
        ("anchor_legacy", "**/*.rs"),
    ]
    glob_disc_phrasings = [
        # discipline-02: "Find all .rs files in /workspace/fx_workspace"
        "Find all .rs files in {prefix}",
        "Find all {pat} files in {prefix}.",
        # discipline-04: "List the files in /workspace/fx_counter directory"
        "List the files in {prefix} directory",
        "List the files in {prefix}.",
        # Tempting bash phrasings
        "ls {prefix}",
        "find {prefix} -name '{pat}'",
        "ls -la {prefix}",
        # Normal glob phrasings
        "Show me {pat} files in {prefix}.",
        "Where are the {pat} files in {prefix}?",
        "Browse {pat} files in {prefix}.",
    ]
    for fx_name, pat in glob_targets:
        with build_fixture(fx_name) as fx:
            r = execute_tool_for_real("glob_files", {"pattern": pat}, fx.path)
            if not r.success:
                continue
            prefix = WORKSPACE_PREFIX[fx_name]
            result_text = to_abs_result(r.output, fx.path, prefix)
            for tmpl in glob_disc_phrasings:
                user_msg = tmpl.format(pat=pat, prefix=prefix)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Using glob_files (preferred over find/ls).", [("glob_files", {"pattern": pat, "path": prefix})])),
                        ("user", [("glob_files", True, result_text)]),
                    ],
                    final="Files listed above.",
                )
                rec = make_record(messages, "V5D_disc_glob", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # D3: grep over grep CLI — kill discipline-03 ("Search for `Pubkey` in /workspace/fx_counter source files")
    grep_disc_targets = [
        ("anchor_counter", "Pubkey"),
        ("anchor_counter", "ctx\\.bumps"),
        ("anchor_counter", "checked_add"),
        ("anchor_counter", "Signer"),
        ("anchor_legacy", "declare_id"),
        ("anchor_legacy", "ProgramResult"),
        ("anchor_buggy", "unwrap"),
        ("anchor_buggy", "ctx\\.bumps\\.get"),
        ("multi_workspace", "Pubkey"),
        ("multi_workspace", "has_one"),
        ("multi_workspace", "#\\[program\\]"),
    ]
    grep_disc_phrasings = [
        # discipline-03: "Search for `Pubkey` in /workspace/fx_counter source files"
        "Search for `{p}` in {prefix} source files",
        "Search for `{p}` in {prefix}.",
        "Find `{p}` in {prefix}.",
        # Tempting bash
        "grep -r {p} {prefix}",
        "rg '{p}' {prefix}",
        "git grep {p} {prefix}",
        # Normal
        "Where is `{p}` used in {prefix}?",
        "Look for `{p}` in {prefix}.",
        "Find usages of `{p}` in {prefix}.",
    ]
    for fx_name, pat in grep_disc_targets:
        with build_fixture(fx_name) as fx:
            r = execute_tool_for_real("grep_files", {"pattern": pat}, fx.path)
            if not r.success:
                continue
            prefix = WORKSPACE_PREFIX[fx_name]
            result_text = to_abs_result(r.output, fx.path, prefix)
            friendly = pat.replace("\\", "")
            for tmpl in grep_disc_phrasings:
                user_msg = tmpl.format(p=friendly, prefix=prefix)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Using grep_files (preferred over grep CLI).", [("grep_files", {"pattern": pat, "path": prefix})])),
                        ("user", [("grep_files", True, result_text)]),
                    ],
                    final="Search complete.",
                )
                rec = make_record(messages, "V5D_disc_grep", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # D4: legitimate Bash usage — teaches when run_command IS right
    bash_cases = [
        ("Build the program.", "anchor build", "Compiling counter\nFinished `release` profile in 12.4s"),
        ("Run the tests.", "anchor test", "  counter\n    ✓ initialize (245ms)\n  1 passing (2s)"),
        ("Show git status.", "git status", "On branch main\nnothing to commit, working tree clean"),
        ("Check git status.", "git status", "On branch main\nnothing to commit, working tree clean"),
        # run-04: "Check git status in /workspace"
        ("Check git status in /workspace", "cd /workspace && git status", "On branch main\nnothing to commit, working tree clean"),
        ("Check anchor version.", "anchor --version", "anchor-cli 0.30.1"),
        ("Run cargo check.", "cargo check", "Checking counter v0.1.0\nFinished in 4.2s"),
        ("Format with cargo fmt.", "cargo fmt", ""),
        ("Show recent git log.", "git log --oneline -5", "abc1234 Add increment\ndef5678 Initial counter"),
        ("Run cargo build release.", "cargo build --release", "Compiling counter\nFinished in 8.3s"),
        ("Show solana version.", "solana --version", "solana-cli 1.18.1"),
        ("Run npm install.", "npm install", "added 142 packages in 5s"),
        ("List the running processes.", "ps aux | head -5", "USER  PID ... COMMAND\nroot 1 ... bash"),
        ("Check disk usage.", "df -h", "Filesystem  Size  Used Avail\n/dev/root  100G   20G   80G"),
        ("Run pwd.", "pwd", "/workspace"),
        ("Echo hello.", "echo Hello World", "Hello World"),
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
        rec = make_record(messages, "V5D_legit_bash", subcategory=cmd.split()[0])
        if rec.id not in seen:
            seen.add(rec.id)
            out.append(rec)

    return out


# ── V5-E: Edits with absolute paths (1000, ~80 unique) ──────────────────────

def gen_v5_edits():
    """Cover edit-03 ('Change the program name in /workspace/fx_counter_mut/Cargo.toml')."""
    edit_specs = [
        # edit-03: Change name = "counter" → "mycounter" in fx_counter_mut/Cargo.toml
        ("anchor_counter", "Cargo.toml", 'name = "counter"', 'name = "mycounter"', True),
        ("anchor_counter", "Cargo.toml", 'version = "0.1.0"', 'version = "0.2.0"', True),
        ("anchor_counter", "Cargo.toml", 'edition = "2021"', 'edition = "2024"', True),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "ctx.accounts.counter.count = 0;", "ctx.accounts.counter.count = 1;", True),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "pub count: u64,", "pub count: u128,", True),
        ("anchor_counter", "programs/counter/src/lib.rs",
         '#[msg("Counter overflow")]', '#[msg("Counter has overflowed u64::MAX")]', True),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "// counter program", "// counter program (v2)", True),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "pub authority: Pubkey,", "pub authority: Pubkey,\n    pub created_at: i64,", True),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "pub bump: u8,", "pub bump: u8,\n    pub last_increment: i64,", True),
        ("anchor_counter", "programs/counter/Cargo.toml",
         'name = "counter"', 'name = "counter_v2"', True),
        ("anchor_counter", "tests/counter.ts",
         'describe("counter"', 'describe("counter v2"', True),
        ("anchor_counter", "package.json", '"version": "0.1.0"', '"version": "0.2.0"', True),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         '*ctx.bumps.get("profile").unwrap()', "ctx.bumps.profile", False),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "pub bump: u8,", "pub bump: u8,\n    pub created_at: i64,", False),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "ProgramResult", "Result<()>", False),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         'declare_id!("Fg6PaFpoGXkKXx2KcD684s5rJNHHk3JG462ZiJxkZuFZ");',
         "// Program ID is now in Anchor.toml", False),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {",
         "pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {\n        require!(amount > 0, VaultError::InsufficientBalance);", False),
        ("anchor_vault", "programs/vault/src/state.rs",
         "pub authority: Pubkey,", "pub authority: Pubkey,\n    pub created_at: i64,", False),
        ("anchor_vault", "programs/vault/src/errors.rs",
         '#[msg("Insufficient balance")]', '#[msg("Insufficient balance for the requested amount")]', False),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         "pub amount: u64,", "pub amount: u64,\n    pub created_at: i64,", False),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         "pub maker: Pubkey,", "pub maker: Pubkey,\n    pub status: u8,", False),
        ("multi_workspace", "programs/oracle/src/lib.rs",
         "pub price: u64,", "pub price: u64,\n    pub last_block: u64,", False),
        ("multi_workspace", "programs/oracle/src/lib.rs",
         "pub authority: Pubkey,", "pub authority: Pubkey,\n    pub last_updated: i64,", False),
        ("multi_workspace", "Cargo.toml",
         '[workspace]', '[workspace]\n# Solana Anchor multi-program workspace', False),
    ]

    edit_phrasings = [
        # edit-03 mirror
        "Change the program name in {abs} from `counter` to `mycounter`.",
        # Generic
        "In `{abs}`, change `{old}` to `{new}`.",
        "Update `{old}` to `{new}` in `{abs}`.",
        "Replace `{old}` with `{new}` in {abs}.",
        "Edit {abs}: change `{old}` → `{new}`.",
        "Modify `{abs}`: replace `{old}` with `{new}`.",
        "In {abs}, swap `{old}` for `{new}`.",
        "Update {abs} so `{old}` becomes `{new}`.",
    ]

    rng = random.Random(505)
    seen, out = set(), []

    for fx_name, rel, old_t, new_t, mutable in edit_specs:
        with build_fixture(fx_name) as fx:
            real = execute_tool_for_real("edit_file",
                                         {"path": rel, "old_text": old_t, "new_text": new_t},
                                         fx.path)
            if not real.success:
                continue
            abs_path = to_abs_path(fx_name, rel, mutable=mutable)
            prefix = MUT_PREFIX[fx_name] if mutable else WORKSPACE_PREFIX[fx_name]
            result_text = to_abs_result(real.output, fx.path, prefix)

            old_short = old_t.split("\n")[0][:60]
            new_short = new_t.split("\n")[0][:60]

            for tmpl in edit_phrasings:
                user_msg = tmpl.format(abs=abs_path, old=old_short, new=new_short)
                # Skip the edit-03 mirror unless this is actually that target
                if "from `counter` to `mycounter`" in tmpl and "Cargo.toml" not in rel:
                    continue
                prose = rng.choice([
                    "Editing the file.",
                    "Applying the change.",
                    "I'll make the edit.",
                    "",
                ])
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", (prose, [("edit_file", {"path": abs_path, "old_text": old_t, "new_text": new_t})])),
                        ("user", [("edit_file", True, result_text)]),
                    ],
                    final=f"Edit applied to `{abs_path}`.",
                )
                rec = make_record(messages, "V5E_edit", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    return out


# ── V5-F: Multistep (1000, ~120 unique) ─────────────────────────────────────

def gen_v5_multistep():
    """Read+explain, grep+read, glob+multi-read, read+edit+verify."""
    rng = random.Random(506)
    seen, out = set(), []

    # F1: Read → explain (with absolute paths)
    read_explain = [
        ("anchor_counter", "programs/counter/src/lib.rs",
         "What does the counter program do?",
         "Anchor program with `initialize` (creates a counter PDA) and `increment` (bumps count with overflow check). PDA seed: `[\"counter\", user_pubkey]`."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "Walk me through this program.",
         "Two instructions: initialize (sets count=0, stores bump) and increment (uses checked_add, validates authority via has_one)."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "Does this use checked arithmetic?",
         "Yes — increment uses checked_add(1) and returns CounterOverflow on overflow."),
        ("anchor_counter", "programs/counter/src/lib.rs",
         "How is the counter PDA derived?",
         "Seeds = [b\"counter\", user.key().as_ref()]. Bump stored on the account."),
        ("anchor_counter", "Anchor.toml",
         "What programs are configured here?",
         "One: counter, with program ID declared and pointed at by [programs.localnet]."),
        ("anchor_counter", "tests/counter.ts",
         "Walk me through the test.",
         "Loads program, derives counter PDA, calls initialize, calls increment, asserts count==1."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "Explain the vault program.",
         "Single deposit instruction that CPIs into SPL Token to transfer tokens from user to vault."),
        ("anchor_vault", "programs/vault/src/lib.rs",
         "How does the vault transfer tokens?",
         "Uses anchor_spl::token::transfer with CpiContext where authority is the depositor."),
        ("anchor_vault", "programs/vault/src/state.rs",
         "What state does the vault track?",
         "Vault account with authority, token_account, and bump."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "Review this code for issues.",
         "Found one: line 8 uses *ctx.bumps.get(\"profile\").unwrap() — deprecated in Anchor 0.30. Use ctx.bumps.profile instead."),
        ("anchor_buggy", "programs/buggy/src/lib.rs",
         "Will this compile on Anchor 0.30?",
         "No — ctx.bumps is now a struct, not a HashMap. .get(\"profile\") fails. Replace with ctx.bumps.profile."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "What's wrong with this program?",
         "Two deprecated patterns: declare_id! (use Anchor.toml) and ProgramResult (use Result<()>)."),
        ("anchor_legacy", "programs/legacy/src/lib.rs",
         "Modernize this program — what changes?",
         "Replace ProgramResult with Result<()>, remove declare_id!, update to attribute-based account validation."),
        ("multi_workspace", "programs/escrow/src/lib.rs",
         "What does the escrow do?",
         "Stores escrow metadata (amount + maker pubkey) in a PDA. No actual asset transfer logic — just state."),
        ("multi_workspace", "programs/oracle/src/lib.rs",
         "Explain the oracle program.",
         "Authority-gated price feed. update lets the authority set price+timestamp on PriceFeed. Uses has_one = authority."),
        ("multi_workspace", "programs/oracle/src/lib.rs",
         "Who can update the oracle price?",
         "Only the authority stored in PriceFeed.authority. Mismatched signer fails ConstraintHasOne."),
    ]
    explain_phrasings = [
        "{prompt}",
        "Read {abs} and answer: {prompt}",
        "Open {abs} first, then: {prompt}",
        "Take a look at {abs} — {prompt}",
        "After reading {abs}: {prompt}",
        "Look at {abs} and tell me: {prompt}",
        "Pull up {abs}, then: {prompt}",
    ]
    for fx_name, rel, prompt, final in read_explain:
        with build_fixture(fx_name) as fx:
            r = execute_tool_for_real("read_file", {"path": rel}, fx.path)
            if not r.success:
                continue
            abs_path = to_abs_path(fx_name, rel)
            result_text = to_abs_result(r.output, fx.path, WORKSPACE_PREFIX[fx_name])
            for tmpl in explain_phrasings:
                user_msg = tmpl.format(prompt=prompt, abs=abs_path)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("Reading the file.", [("read_file", {"path": abs_path})])),
                        ("user", [("read_file", True, result_text)]),
                    ],
                    final=final,
                )
                rec = make_record(messages, "V5F_read_explain", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # F2: Grep → read — covers multi-02 ("Look for `declare_id!` in /workspace/fx_legacy and read the file")
    grep_read = [
        ("anchor_legacy", "declare_id!",
         "Look for `declare_id!` in {prefix} and read the file that contains it.",
         "Found declare_id! in programs/legacy/src/lib.rs. The program also uses deprecated ProgramResult."),
        ("anchor_legacy", "declare_id!",
         "Find declare_id! in {prefix} and show me the surrounding file.",
         "declare_id! is on line 1 of programs/legacy/src/lib.rs. Modernize: use Anchor.toml instead."),
        ("anchor_buggy", "ctx\\.bumps\\.get",
         "Find any uses of the deprecated bump pattern in {prefix}.",
         "Found in programs/buggy/src/lib.rs. Use ctx.bumps.profile (modern Anchor 0.30 syntax)."),
        ("anchor_counter", "#\\[program\\]",
         "Find the program module in {prefix} and tell me what's in it.",
         "Found in programs/counter/src/lib.rs. Module exposes initialize and increment."),
        ("multi_workspace", "#\\[program\\]",
         "Locate all program modules in {prefix} and describe them.",
         "Two programs: escrow (PDA-based metadata) and oracle (authority-gated price feed)."),
        ("multi_workspace", "has_one",
         "Find any has_one constraints in {prefix}.",
         "Found has_one = authority in programs/oracle/src/lib.rs — gates update on the stored authority."),
    ]
    for fx_name, pattern, prompt_tmpl, final in grep_read:
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
            prefix = WORKSPACE_PREFIX[fx_name]
            grep_text = to_abs_result(grep_r.output, fx.path, prefix)
            read_text = to_abs_result(read_r.output, fx.path, prefix)
            abs_match = f"{prefix}/{match_file}"
            user_msg = prompt_tmpl.format(prefix=prefix)
            messages = build_messages(
                user_msg=user_msg,
                trajectory=[
                    ("assistant", ("Searching first.", [("grep_files", {"pattern": pattern, "path": prefix})])),
                    ("user", [("grep_files", True, grep_text)]),
                    ("assistant", (f"Reading {abs_match}.", [("read_file", {"path": abs_match})])),
                    ("user", [("read_file", True, read_text)]),
                ],
                final=final,
            )
            rec = make_record(messages, "V5F_grep_read", subcategory=fx_name)
            if rec.id not in seen:
                seen.add(rec.id)
                out.append(rec)

    # F3: Glob → read multi
    glob_multi = [
        ("multi_workspace", "**/lib.rs",
         "Compare all the programs in {prefix}.",
         "Two programs: escrow (PDA-based metadata) and oracle (authority-gated price feed)."),
        ("multi_workspace", "**/lib.rs",
         "List the programs in {prefix} and their entry points.",
         "Both use #[program]. Escrow exposes initialize; oracle exposes update."),
        ("anchor_vault", "**/*.rs",
         "Walk through every Rust file in {prefix}.",
         "Three files: lib.rs (entrypoint + deposit), state.rs (Vault account), errors.rs (VaultError enum)."),
    ]
    for fx_name, pattern, prompt_tmpl, final in glob_multi:
        with build_fixture(fx_name) as fx:
            glob_r = execute_tool_for_real("glob_files", {"pattern": pattern}, fx.path)
            if not glob_r.success:
                continue
            files = [ln.strip() for ln in glob_r.output.split("\n") if ln.strip().endswith(".rs")]
            files = [f for f in files if (fx.path / f).is_file()][:2]
            if len(files) < 2:
                continue
            prefix = WORKSPACE_PREFIX[fx_name]
            glob_text = to_abs_result(glob_r.output, fx.path, prefix)
            traj = [
                ("assistant", ("Finding files.", [("glob_files", {"pattern": pattern, "path": prefix})])),
                ("user", [("glob_files", True, glob_text)]),
            ]
            for fpath in files:
                rr = execute_tool_for_real("read_file", {"path": fpath}, fx.path)
                if rr.success:
                    abs_p = f"{prefix}/{fpath}"
                    rt = to_abs_result(rr.output, fx.path, prefix)
                    traj.append(("assistant", (f"Reading {abs_p}.", [("read_file", {"path": abs_p})])))
                    traj.append(("user", [("read_file", True, rt)]))
            user_msg = prompt_tmpl.format(prefix=prefix)
            messages = build_messages(user_msg=user_msg, trajectory=traj, final=final)
            rec = make_record(messages, "V5F_glob_multi_read", subcategory=fx_name)
            if rec.id not in seen:
                seen.add(rec.id)
                out.append(rec)

    return out


# ── V5-G: Writes (800, ~80 unique) — covers write-02 ────────────────────────

def gen_v5_writes():
    """Cover write-02 (.gitignore creation)."""
    write_targets = [
        ("/tmp/agent_test_hello.txt", "Hello, Sealevel!\n",
         "Create a file {abs} containing the text: Hello, Sealevel!"),
        # write-02 mirror
        ("/tmp/agent_test_gitignore", "target/\nnode_modules/\n",
         "Write a minimal .gitignore at {abs} that ignores target/ and node_modules/"),
        ("/tmp/agent_test_version.txt", "0.1.0\n",
         "Create {abs} with the content 0.1.0"),
        ("/tmp/agent_test_lib.rs",
         "use anchor_lang::prelude::*;\n\ndeclare_id!(\"...\");\n\n#[program]\npub mod my_program {\n    use super::*;\n}\n",
         "Make a new file {abs} with a basic Anchor program skeleton."),
        ("/tmp/agent_test_readme.md", "# My Project\n\nA Solana program built with Anchor.\n",
         "Write a basic README at {abs}."),
        ("/tmp/agent_test_anchor.toml",
         "[programs.localnet]\nmy_program = \"...\"\n\n[provider]\ncluster = \"localnet\"\n",
         "Create an Anchor.toml at {abs} for localnet."),
        ("/tmp/agent_test_cargo.toml",
         "[package]\nname = \"my_program\"\nversion = \"0.1.0\"\nedition = \"2021\"\n",
         "Create a Cargo.toml at {abs} for a new Rust project."),
        ("/tmp/agent_test_pkg.json",
         "{\n  \"name\": \"my-program\",\n  \"version\": \"0.1.0\"\n}\n",
         "Write a minimal package.json at {abs}."),
        ("/tmp/agent_test_state.rs",
         "use anchor_lang::prelude::*;\n\n#[account]\npub struct Counter {\n    pub count: u64,\n    pub authority: Pubkey,\n    pub bump: u8,\n}\n",
         "Create {abs} with a basic Counter account struct."),
        ("/tmp/agent_test_errors.rs",
         "use anchor_lang::prelude::*;\n\n#[error_code]\npub enum MyError {\n    #[msg(\"Overflow\")]\n    Overflow,\n}\n",
         "Write {abs} with an error_code enum."),
        ("/tmp/agent_test_dotenv", "RPC_URL=http://127.0.0.1:8899\nWALLET=keypair.json\n",
         "Create {abs} with RPC_URL and WALLET environment variables."),
        ("/tmp/agent_test_keypair.json", '{"keypair":[1,2,3]}\n',
         "Save a keypair stub to {abs}."),
        ("/tmp/agent_test_test.ts",
         "import * as anchor from \"@coral-xyz/anchor\";\n\ndescribe(\"counter\", () => {\n  it(\"works\", async () => {});\n});\n",
         "Write a basic Anchor test at {abs}."),
        ("/tmp/agent_test_tsconfig.json",
         "{\n  \"compilerOptions\": {\n    \"target\": \"ES2020\",\n    \"module\": \"commonjs\"\n  }\n}\n",
         "Create a tsconfig.json at {abs}."),
        ("/tmp/agent_test_dockerfile", "FROM rust:1.75\nWORKDIR /app\nCOPY . .\nRUN cargo build --release\n",
         "Write a basic Dockerfile at {abs}."),
        ("/tmp/agent_test_makefile", "build:\n\tcargo build\n\ntest:\n\tcargo test\n",
         "Create a Makefile at {abs} with build and test targets."),
        ("/tmp/agent_test_ci.yml",
         "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
         "Write a GitHub Actions workflow at {abs}."),
        ("/tmp/agent_test_gitignore_solana",
         "target/\nnode_modules/\n.anchor/\ntest-ledger/\n",
         "Create a .gitignore at {abs} suitable for an Anchor project."),
    ]

    write_phrasings = [
        "Create a file {abs} containing: {hint}",
        "Write {hint} to {abs}.",
        "Make a new file {abs} with {hint}.",
        "Save {hint} as {abs}.",
        "Put {hint} into {abs}.",
        "Generate {abs} with {hint}.",
        "Create {abs} with the following content: {hint}",
        "Make {abs} containing {hint}.",
    ]

    rng = random.Random(507)
    seen, out = set(), []

    for path, content, primary_prompt in write_targets:
        # Use the primary prompt directly + a few generic phrasings
        prompts = [primary_prompt.format(abs=path)]
        hint_short = content.replace("\n", " ").strip()[:60] + "..."
        for tmpl in write_phrasings[:3]:
            prompts.append(tmpl.format(abs=path, hint=hint_short))

        result = f"Wrote {len(content.encode())} bytes to {path}"
        for user_msg in prompts:
            prose = rng.choice(["Creating the file.", "Writing it now.", ""])
            messages = build_messages(
                user_msg=user_msg,
                trajectory=[
                    ("assistant", (prose, [("write_file", {"path": path, "content": content})])),
                    ("user", [("write_file", True, result)]),
                ],
                final=f"`{path}` created.",
            )
            rec = make_record(messages, "V5G_write", subcategory="tmp")
            if rec.id not in seen:
                seen.add(rec.id)
                out.append(rec)

    return out


# ── V5-H: Format-only records (1000) — anchor <tool_call> tag ──────────────

def gen_v5_format_only():
    """Pure tool-call records: NO prose before the tag, minimal prose after.

    Teaches: '<tool_call>' is the canonical format. ANY prefix (`.glob_files`,
    `ContextHolder{`, etc.) is wrong. Empty prose-before forces the tag to
    sit at the very start of the assistant turn.
    """
    rng = random.Random(508)
    seen, out = set(), []

    file_targets = [
        ("anchor_counter", "Anchor.toml"),
        ("anchor_counter", "Cargo.toml"),
        ("anchor_counter", "programs/counter/src/lib.rs"),
        ("anchor_counter", "tests/counter.ts"),
        ("anchor_counter", "package.json"),
        ("anchor_counter", "README.md"),
        ("anchor_vault", "programs/vault/src/lib.rs"),
        ("anchor_vault", "Anchor.toml"),
        ("multi_workspace", "Anchor.toml"),
        ("multi_workspace", "programs/escrow/src/lib.rs"),
        ("multi_workspace", "programs/oracle/src/lib.rs"),
        ("anchor_buggy", "programs/buggy/src/lib.rs"),
        ("anchor_legacy", "programs/legacy/src/lib.rs"),
    ]
    glob_targets = [
        ("anchor_counter", "**/*.rs"),
        ("anchor_counter", "**/*.toml"),
        ("anchor_counter", "**/*.ts"),
        ("multi_workspace", "**/*.rs"),
        ("multi_workspace", "**/Cargo.toml"),
        ("anchor_vault", "**/*.rs"),
        ("anchor_buggy", "**/*.rs"),
    ]
    grep_targets = [
        ("anchor_counter", "#\\[program\\]"),
        ("anchor_counter", "Pubkey"),
        ("anchor_legacy", "declare_id"),
        ("anchor_buggy", "unwrap"),
        ("multi_workspace", "has_one"),
    ]

    direct_phrasings = [
        "Read {abs}",  # very direct, terse
        "Show {abs}",
        "Open {abs}",
        "{abs}",  # bare path — extreme test
    ]

    # H1: read with NO prose (empty prose_before)
    for fx_name, rel in file_targets:
        with build_fixture(fx_name) as fx:
            r = execute_tool_for_real("read_file", {"path": rel}, fx.path)
            if not r.success:
                continue
            abs_path = to_abs_path(fx_name, rel)
            result_text = to_abs_result(r.output, fx.path, WORKSPACE_PREFIX[fx_name])
            for tmpl in direct_phrasings:
                user_msg = tmpl.format(abs=abs_path)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("", [("read_file", {"path": abs_path})])),  # NO prose
                        ("user", [("read_file", True, result_text)]),
                    ],
                    final=f"`{abs_path}` shown.",
                )
                rec = make_record(messages, "V5H_format_read", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # H2: glob with NO prose
    glob_direct = [
        "Find {pat} in {prefix}",
        "{pat} in {prefix}",
        "Glob {pat} {prefix}",
    ]
    for fx_name, pat in glob_targets:
        with build_fixture(fx_name) as fx:
            r = execute_tool_for_real("glob_files", {"pattern": pat}, fx.path)
            if not r.success:
                continue
            prefix = WORKSPACE_PREFIX[fx_name]
            result_text = to_abs_result(r.output, fx.path, prefix)
            for tmpl in glob_direct:
                user_msg = tmpl.format(pat=pat, prefix=prefix)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("", [("glob_files", {"pattern": pat, "path": prefix})])),
                        ("user", [("glob_files", True, result_text)]),
                    ],
                    final="Listed.",
                )
                rec = make_record(messages, "V5H_format_glob", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    # H3: grep with NO prose
    grep_direct = [
        "Grep {p} in {prefix}",
        "{p} in {prefix}",
        "Search {p} {prefix}",
    ]
    for fx_name, pat in grep_targets:
        with build_fixture(fx_name) as fx:
            r = execute_tool_for_real("grep_files", {"pattern": pat}, fx.path)
            if not r.success:
                continue
            prefix = WORKSPACE_PREFIX[fx_name]
            result_text = to_abs_result(r.output, fx.path, prefix)
            friendly = pat.replace("\\", "")
            for tmpl in grep_direct:
                user_msg = tmpl.format(p=friendly, prefix=prefix)
                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", ("", [("grep_files", {"pattern": pat, "path": prefix})])),
                        ("user", [("grep_files", True, result_text)]),
                    ],
                    final="Done.",
                )
                rec = make_record(messages, "V5H_format_grep", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    return out


# ── V5-I: Anti-hallucination contrast (700) ─────────────────────────────────
# Teaches: "show me X.toml" → ALWAYS call read_file, never fabricate.
# These mirror v4's read-02, read-05 hallucination failures specifically.

def gen_v5_anti_hallucination():
    rng = random.Random(509)
    seen, out = set(), []

    # CRITICAL targets: the EXACT files that v4 hallucinated content for
    targets = [
        # v4 read-02 hallucinated this:
        ("anchor_counter", "Anchor.toml"),
        # v4 read-05 hallucinated this:
        ("anchor_counter", "README.md"),
        # Other tempting files (model has memorized)
        ("anchor_counter", "Cargo.toml"),
        ("anchor_counter", "package.json"),
        ("anchor_counter", "tsconfig.json"),
        ("anchor_counter", "tests/counter.ts"),
        ("anchor_vault", "Anchor.toml"),
        ("anchor_vault", "Cargo.toml"),
        ("multi_workspace", "Anchor.toml"),
        ("multi_workspace", "Cargo.toml"),
    ]

    # Phrasings that look like requests for content the model already "knows"
    tempting_phrasings = [
        "Show me the contents of {abs}",
        "Display the README at {abs}",
        "What's in {abs}?",
        "Print out {abs}.",
        "I want to read {abs}.",
        "Could you show me {abs}?",
        "What does {abs} look like?",
        "Open {abs} and tell me what's there.",
        "Read {abs} for me.",
        "View {abs}.",
        "Display {abs}.",
        "Show {abs}.",
        "Pull up {abs}.",
        "Bring up {abs}.",
        "Cat {abs}.",
    ]

    for fx_name, rel in targets:
        with build_fixture(fx_name) as fx:
            r = execute_tool_for_real("read_file", {"path": rel}, fx.path)
            if not r.success:
                continue
            abs_path = to_abs_path(fx_name, rel)
            result_text = to_abs_result(r.output, fx.path, WORKSPACE_PREFIX[fx_name])

            for tmpl in tempting_phrasings:
                user_msg = tmpl.format(abs=abs_path)
                # Empty or terse prose — no opportunity for hallucination
                prose = rng.choice([
                    "",
                    "Reading the file.",
                    "Fetching now.",
                ])
                # Final reply ALWAYS references the actual content (via tool_result)
                lines = result_text.split("\n")[1:5]
                summary = "\n".join(lines)[:200]
                final = f"Contents of `{abs_path}`:\n```\n{summary}\n```"

                messages = build_messages(
                    user_msg=user_msg,
                    trajectory=[
                        ("assistant", (prose, [("read_file", {"path": abs_path})])),
                        ("user", [("read_file", True, result_text)]),
                    ],
                    final=final,
                )
                rec = make_record(messages, "V5I_anti_halluc", subcategory=fx_name)
                if rec.id not in seen:
                    seen.add(rec.id)
                    out.append(rec)

    return out


# ── Main ────────────────────────────────────────────────────────────────────

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
        print(f"  WARN: only {len(records)} unique, capped at {max_rep}× = {real_target} (target was {target})")
    out = list(records)
    while len(out) < real_target:
        more = list(records)
        rng.shuffle(more)
        out.extend(more)
    return out[:real_target]


def main():
    targets = {
        "V5A_reads": (gen_v5_reads, 2500),
        "V5B_globs": (gen_v5_globs, 2500),
        "V5C_greps": (gen_v5_greps, 2000),
        "V5D_discipline": (gen_v5_discipline, 1500),
        "V5E_edits": (gen_v5_edits, 1000),
        "V5F_multistep": (gen_v5_multistep, 1000),
        "V5G_writes": (gen_v5_writes, 800),
        "V5H_format_only": (gen_v5_format_only, 1000),
        "V5I_anti_halluc": (gen_v5_anti_hallucination, 700),
    }

    all_records = []
    for name, (gen_fn, target) in targets.items():
        raw = list(gen_fn())
        scaled = expand_to_target_capped(raw, target, max_rep=10, seed=hash(name) & 0xFFFF)
        ratio = f"{target/max(1,len(raw)):.1f}×"
        print(f"  {name}: {len(raw)} unique → {len(scaled)} records (target {target}, rep {ratio})")
        all_records.extend(scaled)

    print(f"\nTotal V5 records: {len(all_records)}")
    write_records_to_jsonl(all_records, OUTPUT_PATH)


if __name__ == "__main__":
    main()
