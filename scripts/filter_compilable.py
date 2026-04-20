#!/usr/bin/env python3
"""
filter_compilable.py — Split SFT training data by Anchor/Rust compilability.

Reads sft_train.jsonl and produces three output files:
  - sft_compilable.jsonl    (assistant code compiles with anchor-lang 0.32)
  - sft_noncompilable.jsonl (assistant code fails to compile)
  - sft_nocode.jsonl        (no Rust code blocks in assistant response)

Requires an Anchor project scaffold at /tmp/slm-bench/bench_project.
"""

import json
import os
import re
import subprocess
import tempfile
import shutil
from multiprocessing import Pool
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "final"
INPUT_FILE = DATA_DIR / "sft_train.jsonl"
OUT_COMPILABLE = DATA_DIR / "sft_compilable.jsonl"
OUT_NONCOMPILABLE = DATA_DIR / "sft_noncompilable.jsonl"
OUT_NOCODE = DATA_DIR / "sft_nocode.jsonl"

BENCH_BASE = Path("/tmp/slm-bench/bench_project")
LIB_RS_REL = "programs/bench_project/src/lib.rs"
CARGO_TOML_REL = "programs/bench_project/Cargo.toml"

NUM_WORKERS = 4
COMPILE_TIMEOUT = 30  # seconds

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RUST_CODE_BLOCK_RE = re.compile(
    r"```(?:rust|rs|anchor)?\s*\n(.*?)```", re.DOTALL
)

ANCHOR_USE = "use anchor_lang::prelude::*;"
DECLARE_ID = 'declare_id!("11111111111111111111111111111111");'


def extract_rust_blocks(messages: list[dict]) -> list[str]:
    """Return all Rust code blocks found in assistant messages."""
    blocks = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        blocks.extend(RUST_CODE_BLOCK_RE.findall(content))
    return [b.strip() for b in blocks if b.strip()]


def _prep_code(code: str) -> str:
    """Auto-prepend anchor imports / declare_id if missing."""
    lines = []
    has_use = "use anchor_lang::prelude::*" in code
    has_declare = "declare_id!" in code

    if not has_use:
        lines.append(ANCHOR_USE)
    if not has_declare:
        lines.append(DECLARE_ID)
    if lines:
        lines.append("")  # blank separator
    lines.append(code)
    return "\n".join(lines)


def try_compile(args: tuple) -> tuple:
    """
    Compile a single example's Rust code blocks.

    Returns (index, json_line, category)
      category: "compilable" | "noncompilable" | "nocode"

    Each worker gets its own copy of the bench project so workers don't
    stomp on each other.
    """
    idx, line = args
    record = json.loads(line)
    messages = record.get("messages", [])
    blocks = extract_rust_blocks(messages)

    if not blocks:
        return (idx, line, "nocode")

    # Create a per-worker copy of the project
    worker_dir = Path(tempfile.mkdtemp(prefix=f"slm-bench-{idx}-"))
    try:
        # Copy the bench project scaffold
        dest = worker_dir / "bench_project"
        shutil.copytree(str(BENCH_BASE), str(dest))

        lib_rs = dest / LIB_RS_REL
        cargo_toml = dest / CARGO_TOML_REL

        for block in blocks:
            code = _prep_code(block)
            lib_rs.write_text(code)

            try:
                result = subprocess.run(
                    [
                        "cargo",
                        "check",
                        "--manifest-path",
                        str(cargo_toml),
                    ],
                    capture_output=True,
                    timeout=COMPILE_TIMEOUT,
                )
                if result.returncode != 0:
                    return (idx, line, "noncompilable")
            except subprocess.TimeoutExpired:
                return (idx, line, "noncompilable")
            except Exception:
                return (idx, line, "noncompilable")

        # All blocks compiled
        return (idx, line, "compilable")
    finally:
        shutil.rmtree(worker_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_already_processed() -> set[str]:
    """
    For idempotency: gather the set of JSON lines already written to
    any of the three output files so we can skip them.
    """
    seen = set()
    for path in (OUT_COMPILABLE, OUT_NONCOMPILABLE, OUT_NOCODE):
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        seen.add(line)
    return seen


def main():
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        return

    if not BENCH_BASE.exists():
        print(f"ERROR: Bench project not found at {BENCH_BASE}")
        return

    # Read input
    with open(INPUT_FILE) as f:
        all_lines = [l.strip() for l in f if l.strip()]

    total = len(all_lines)
    print(f"Loaded {total} examples from {INPUT_FILE}")

    # Idempotency — figure out what's already been processed
    already = _load_already_processed()
    to_process = []
    pre_sorted = {"compilable": [], "noncompilable": [], "nocode": []}

    for idx, line in enumerate(all_lines):
        if line in already:
            # Already in an output file; we don't know which bucket,
            # so re-check quickly (no-code is cheap, the rest we skip).
            # Actually, just skip entirely — the line is already written.
            pass
        else:
            to_process.append((idx, line))

    skipped = total - len(to_process)
    if skipped:
        print(f"Skipping {skipped} already-processed examples")

    if not to_process:
        print("Nothing to process.")
        _print_stats()
        return

    print(f"Processing {len(to_process)} examples with {NUM_WORKERS} workers...")

    # Try to use tqdm
    try:
        from tqdm import tqdm
        use_tqdm = True
    except ImportError:
        use_tqdm = False

    results = {"compilable": [], "noncompilable": [], "nocode": []}

    with Pool(NUM_WORKERS) as pool:
        iterator = pool.imap_unordered(try_compile, to_process)
        if use_tqdm:
            iterator = tqdm(iterator, total=len(to_process), desc="Compiling")

        for i, (idx, line, category) in enumerate(iterator):
            results[category].append(line)
            if not use_tqdm and (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(to_process)}...")

    # Append to output files (append mode for idempotency)
    for category, path in [
        ("compilable", OUT_COMPILABLE),
        ("noncompilable", OUT_NONCOMPILABLE),
        ("nocode", OUT_NOCODE),
    ]:
        if results[category]:
            with open(path, "a") as f:
                for line in results[category]:
                    f.write(line + "\n")

    _print_stats()


def _print_stats():
    """Print final counts from the output files."""
    def _count(p):
        if not p.exists():
            return 0
        with open(p) as f:
            return sum(1 for l in f if l.strip())

    c = _count(OUT_COMPILABLE)
    nc = _count(OUT_NONCOMPILABLE)
    no = _count(OUT_NOCODE)
    t = c + nc + no

    print("\n===== Filter Results =====")
    print(f"  Total:           {t}")
    print(f"  Compilable:      {c}  ({100*c/t:.1f}%)" if t else "  Compilable:      0")
    print(f"  Non-compilable:  {nc}  ({100*nc/t:.1f}%)" if t else "  Non-compilable:  0")
    print(f"  No code:         {no}  ({100*no/t:.1f}%)" if t else "  No code:         0")
    print(f"\nOutputs:")
    print(f"  {OUT_COMPILABLE}")
    print(f"  {OUT_NONCOMPILABLE}")
    print(f"  {OUT_NOCODE}")


if __name__ == "__main__":
    main()
