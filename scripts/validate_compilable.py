#!/usr/bin/env python3
"""
validate_compilable.py — Multi-framework compile validation for SFT records.

Validates that Rust code in ChatML SFT examples actually compiles, supporting
Anchor, Pinocchio, and native Solana programs.  Non-compilable code goes through
up to 3 auto-repair attempts before being discarded.

Outputs:
  data/validated/sft_compilable.jsonl      — records whose code compiles
  data/validated/sft_noncompilable.jsonl    — records that failed compilation
  data/validated/sft_nocode.jsonl           — records with no extractable Rust
  data/validated/compile_report.json        — aggregate statistics
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from schema import detect_framework

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "sft-code-write.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "data" / "validated"

BENCH_BASE = Path("/tmp/slm-bench")
COMPILE_TIMEOUT = 60  # seconds

RUST_CODE_BLOCK_RE = re.compile(
    r"```(?:rust|rs|anchor)?\s*\n(.*?)```", re.DOTALL
)

# Minimum non-whitespace / non-comment content to be considered real code
MIN_CODE_CHARS = 20

# ---------------------------------------------------------------------------
# Scaffold definitions
# ---------------------------------------------------------------------------

SCAFFOLDS: dict[str, dict] = {
    "anchor": {
        "dir": "anchor_project",
        "cargo_toml": """\
[package]
name = "anchor_project"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "lib"]

[dependencies]
anchor-lang = { version = "0.32", features = ["init-if-needed"] }
anchor-spl = { version = "0.32", features = ["token", "associated-token"] }
""",
        "lib_rs": "// placeholder\n",
    },
    "pinocchio": {
        "dir": "pinocchio_project",
        "cargo_toml": """\
[package]
name = "pinocchio_project"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "lib"]

[dependencies]
pinocchio = "0.7"
pinocchio-token = "0.4"
""",
        "lib_rs": "// placeholder\n",
    },
    "native": {
        "dir": "native_project",
        "cargo_toml": """\
[package]
name = "native_project"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "lib"]

[dependencies]
solana-program = "2.0"
""",
        "lib_rs": "// placeholder\n",
    },
}

# ---------------------------------------------------------------------------
# Auto-repair rules (framework -> list of (condition, prepend_line))
# ---------------------------------------------------------------------------

REPAIR_RULES: dict[str, list[tuple[str, str]]] = {
    "anchor": [
        (
            lambda code: "use anchor_lang::prelude::*" not in code,
            "use anchor_lang::prelude::*;",
        ),
        (
            lambda code: any(
                t in code for t in ("Token", "TokenAccount", "Mint")
            )
            and "use anchor_spl::token" not in code,
            "use anchor_spl::token::{Token, TokenAccount, Mint};",
        ),
        (
            lambda code: "declare_id!" not in code
            and "declare_program!" not in code,
            'declare_id!("11111111111111111111111111111111");',
        ),
    ],
    "pinocchio": [
        (
            lambda code: "use pinocchio" not in code,
            "use pinocchio::prelude::*;",
        ),
    ],
    "native": [
        (
            lambda code: "use solana_program" not in code,
            "use solana_program::{account_info::AccountInfo, entrypoint, entrypoint::ProgramResult, pubkey::Pubkey, msg};",
        ),
    ],
}


# ---------------------------------------------------------------------------
# Scaffold setup
# ---------------------------------------------------------------------------

def ensure_scaffolds() -> None:
    """Create / refresh the three scaffold projects under /tmp/slm-bench/."""
    BENCH_BASE.mkdir(parents=True, exist_ok=True)
    for framework, spec in SCAFFOLDS.items():
        proj_dir = BENCH_BASE / spec["dir"]
        src_dir = proj_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)

        cargo_path = proj_dir / "Cargo.toml"
        lib_path = src_dir / "lib.rs"

        # Always rewrite Cargo.toml to pick up dependency changes
        cargo_path.write_text(spec["cargo_toml"])
        lib_path.write_text(spec["lib_rs"])

    # Pre-fetch dependencies for each scaffold so workers don't race
    console = Console(stderr=True)
    for framework, spec in SCAFFOLDS.items():
        proj_dir = BENCH_BASE / spec["dir"]
        cargo_path = proj_dir / "Cargo.toml"
        console.print(f"  [dim]Pre-fetching deps for {framework}...[/dim]")
        subprocess.run(
            ["cargo", "check", "--manifest-path", str(cargo_path)],
            capture_output=True,
            timeout=120,
        )


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------

def extract_rust_blocks(messages: list[dict]) -> list[str]:
    """Return all Rust code blocks found in assistant messages."""
    blocks: list[str] = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        found = RUST_CODE_BLOCK_RE.findall(content)
        blocks.extend(found)

        # Fallback: if no fenced blocks, check if whole content looks like Rust
        if not found and _looks_like_rust(content):
            blocks.append(content)

    return [b.strip() for b in blocks if b.strip()]


def _looks_like_rust(text: str) -> bool:
    """Heuristic: does the text look like raw Rust source code?"""
    rust_signals = ["fn ", "struct ", "impl ", "pub fn ", "use ", "#[", "mod "]
    score = sum(1 for s in rust_signals if s in text)
    return score >= 3


def _is_real_code(code: str) -> bool:
    """Filter out blocks that are just comments or whitespace."""
    stripped = re.sub(r"//[^\n]*", "", code)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
    stripped = re.sub(r"\s+", "", stripped)
    return len(stripped) >= MIN_CODE_CHARS


# ---------------------------------------------------------------------------
# Auto-repair
# ---------------------------------------------------------------------------

def apply_repairs(code: str, framework: str) -> str:
    """Apply all matching repair rules and return the patched code."""
    rules = REPAIR_RULES.get(framework, [])
    prepends: list[str] = []
    for condition_fn, line in rules:
        if condition_fn(code):
            prepends.append(line)
    if prepends:
        return "\n".join(prepends) + "\n\n" + code
    return code


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------

def _compile_code(
    code: str,
    framework: str,
    worker_dir: Path,
) -> tuple[bool, str]:
    """Write code into the scaffold and run `cargo check`.

    Returns (success, stderr).
    """
    spec = SCAFFOLDS[framework]
    proj_name = spec["dir"]

    # Copy scaffold into worker dir if not already there
    dest = worker_dir / proj_name
    if not dest.exists():
        shutil.copytree(str(BENCH_BASE / proj_name), str(dest))

    lib_rs = dest / "src" / "lib.rs"
    cargo_toml = dest / "Cargo.toml"

    lib_rs.write_text(code)
    try:
        result = subprocess.run(
            ["cargo", "check", "--manifest-path", str(cargo_toml)],
            capture_output=True,
            timeout=COMPILE_TIMEOUT,
            text=True,
        )
        return result.returncode == 0, result.stderr
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as exc:
        return False, str(exc)


MAX_REPAIR_ATTEMPTS = 3


def try_compile_record(args: tuple) -> tuple:
    """Compile all Rust blocks in a single SFT record.

    Returns (index, json_line, category, compile_status)
      category:       "compilable" | "noncompilable" | "nocode"
      compile_status: "pass" | "fixed" | "fail" | "nocode"
    """
    idx, line = args
    record = json.loads(line)
    messages = record.get("messages", [])
    blocks = extract_rust_blocks(messages)

    # Filter out non-real code
    blocks = [b for b in blocks if _is_real_code(b)]

    if not blocks:
        return (idx, line, "nocode", "nocode")

    worker_dir = Path(tempfile.mkdtemp(prefix=f"slm-val-{idx}-"))
    try:
        for block in blocks:
            framework = detect_framework(block)
            compiled, fixed = _try_compile_with_repairs(
                block, framework, worker_dir
            )
            if not compiled:
                return (idx, line, "noncompilable", "fail")
            if fixed:
                # At least one block needed repair; mark as "fixed"
                # (we still count it as compilable)
                pass

        # Determine overall status
        # Re-check if any block was fixed
        all_fixed = False
        for block in blocks:
            framework = detect_framework(block)
            ok_raw, _ = _compile_code(block, framework, worker_dir)
            if not ok_raw:
                all_fixed = True
                break

        status = "fixed" if all_fixed else "pass"
        return (idx, line, "compilable", status)
    finally:
        shutil.rmtree(worker_dir, ignore_errors=True)


def _try_compile_with_repairs(
    code: str,
    framework: str,
    worker_dir: Path,
) -> tuple[bool, bool]:
    """Try compiling code, applying incremental repairs up to MAX_REPAIR_ATTEMPTS.

    Returns (compiled_ok, was_fixed).
    """
    # Attempt 0: raw code
    ok, stderr = _compile_code(code, framework, worker_dir)
    if ok:
        return True, False

    # Attempt 1: apply standard repairs
    repaired = apply_repairs(code, framework)
    if repaired != code:
        ok, stderr = _compile_code(repaired, framework, worker_dir)
        if ok:
            return True, True

    # Attempt 2: try with all frameworks' base imports
    full_imports = apply_repairs(code, framework)
    # Also try adding common missing items based on error messages
    if "cannot find" in stderr or "unresolved import" in stderr:
        extra = _guess_extra_imports(stderr, framework)
        if extra:
            candidate = extra + "\n" + full_imports
            ok, stderr = _compile_code(candidate, framework, worker_dir)
            if ok:
                return True, True

    # Attempt 3: try alternative framework if detection might be wrong
    alt_frameworks = [f for f in SCAFFOLDS if f != framework]
    for alt in alt_frameworks:
        alt_code = apply_repairs(code, alt)
        ok, _ = _compile_code(alt_code, alt, worker_dir)
        if ok:
            return True, True

    return False, False


def _guess_extra_imports(stderr: str, framework: str) -> str:
    """Try to guess missing imports from compiler error output."""
    extras: list[str] = []
    if framework == "anchor":
        if "AssociatedToken" in stderr:
            extras.append(
                "use anchor_spl::associated_token::AssociatedToken;"
            )
        if "Transfer" in stderr and "anchor_spl::token::Transfer" not in stderr:
            extras.append("use anchor_spl::token::Transfer;")
        if "CpiContext" in stderr:
            extras.append("use anchor_lang::prelude::*;")
        if "System" in stderr or "system_program" in stderr:
            extras.append("use anchor_lang::system_program;")
    elif framework == "native":
        if "AccountInfo" in stderr:
            extras.append(
                "use solana_program::account_info::{next_account_info, AccountInfo};"
            )
        if "ProgramError" in stderr:
            extras.append("use solana_program::program_error::ProgramError;")
        if "Pubkey" in stderr:
            extras.append("use solana_program::pubkey::Pubkey;")
    return "\n".join(extras)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(
    stats: dict,
    output_dir: Path,
    elapsed: float,
) -> None:
    """Write compile_report.json with aggregate statistics."""
    total = stats["pass"] + stats["fixed"] + stats["fail"] + stats["nocode"]
    compilable = stats["pass"] + stats["fixed"]
    report = {
        "total_records": total,
        "compilable": compilable,
        "compilable_pass": stats["pass"],
        "compilable_fixed": stats["fixed"],
        "noncompilable": stats["fail"],
        "nocode": stats["nocode"],
        "compile_rate_pct": round(100 * compilable / total, 2) if total else 0,
        "elapsed_seconds": round(elapsed, 1),
    }
    report_path = output_dir / "compile_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")


def print_summary(stats: dict, elapsed: float, console: Console) -> None:
    """Print a rich summary table."""
    total = stats["pass"] + stats["fixed"] + stats["fail"] + stats["nocode"]
    compilable = stats["pass"] + stats["fixed"]

    table = Table(title="Compile Validation Results", show_lines=True)
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percent", justify="right")

    def pct(n: int) -> str:
        return f"{100 * n / total:.1f}%" if total else "0%"

    table.add_row("Total", str(total), "100%")
    table.add_row("Compilable (pass)", str(stats["pass"]), pct(stats["pass"]))
    table.add_row("Compilable (fixed)", str(stats["fixed"]), pct(stats["fixed"]))
    table.add_row(
        "Compilable (total)",
        str(compilable),
        pct(compilable),
        style="green",
    )
    table.add_row("Non-compilable", str(stats["fail"]), pct(stats["fail"]), style="red")
    table.add_row("No code", str(stats["nocode"]), pct(stats["nocode"]), style="dim")

    console.print()
    console.print(table)
    console.print(f"\n  Elapsed: {elapsed:.1f}s")
    console.print(f"  Output:  {OUTPUT_DIR}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

app = typer.Typer(help="Multi-framework compile validation for SFT records.")


@app.command()
def main(
    input: Path = typer.Option(
        DEFAULT_INPUT, "--input", "-i", help="Input JSONL file with ChatML records."
    ),
    workers: int = typer.Option(
        4, "--workers", "-w", help="Number of parallel compilation workers."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Count and categorize without compiling."
    ),
) -> None:
    """Validate that SFT code examples compile across Solana frameworks."""
    console = Console()

    if not input.exists():
        console.print(f"[red]ERROR:[/red] Input file not found: {input}")
        raise typer.Exit(1)

    # Load records
    with open(input) as f:
        all_lines = [l.strip() for l in f if l.strip()]

    total = len(all_lines)
    console.print(f"Loaded [bold]{total}[/bold] records from {input}")

    if total == 0:
        console.print("[yellow]Nothing to process.[/yellow]")
        raise typer.Exit(0)

    # Dry-run mode: just categorize by code presence and framework
    if dry_run:
        _dry_run(all_lines, console)
        raise typer.Exit(0)

    # Ensure scaffold projects exist
    console.print("Setting up scaffold projects...")
    ensure_scaffolds()

    # Prepare output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_compilable = OUTPUT_DIR / "sft_compilable.jsonl"
    out_noncompilable = OUTPUT_DIR / "sft_noncompilable.jsonl"
    out_nocode = OUTPUT_DIR / "sft_nocode.jsonl"

    # Process
    indexed_lines = list(enumerate(all_lines))
    stats = {"pass": 0, "fixed": 0, "fail": 0, "nocode": 0}
    buckets: dict[str, list[str]] = {
        "compilable": [],
        "noncompilable": [],
        "nocode": [],
    }

    t0 = time.time()
    console.print(
        f"Compiling with [bold]{workers}[/bold] workers "
        f"(timeout {COMPILE_TIMEOUT}s per record)..."
    )

    with Pool(workers) as pool:
        results = pool.imap_unordered(try_compile_record, indexed_lines)
        for idx, line, category, status in track(
            results, total=total, description="Validating..."
        ):
            stats[status] += 1
            buckets[category].append(line)

    elapsed = time.time() - t0

    # Write outputs
    for category, path in [
        ("compilable", out_compilable),
        ("noncompilable", out_noncompilable),
        ("nocode", out_nocode),
    ]:
        with open(path, "w") as f:
            for line in buckets[category]:
                f.write(line + "\n")

    write_report(stats, OUTPUT_DIR, elapsed)
    print_summary(stats, elapsed, console)


def _dry_run(all_lines: list[str], console: Console) -> None:
    """Quick categorization without compiling."""
    stats = {"has_code": 0, "nocode": 0}
    framework_counts: dict[str, int] = {"anchor": 0, "pinocchio": 0, "native": 0}

    for line in track(all_lines, description="Categorizing..."):
        record = json.loads(line)
        messages = record.get("messages", [])
        blocks = extract_rust_blocks(messages)
        blocks = [b for b in blocks if _is_real_code(b)]

        if not blocks:
            stats["nocode"] += 1
            continue

        stats["has_code"] += 1
        for block in blocks:
            fw = detect_framework(block)
            framework_counts[fw] += 1

    table = Table(title="Dry Run Summary", show_lines=True)
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")

    total = stats["has_code"] + stats["nocode"]
    table.add_row("Total records", str(total))
    table.add_row("Records with code", str(stats["has_code"]))
    table.add_row("Records without code", str(stats["nocode"]))
    table.add_row("---", "---")
    table.add_row("Anchor code blocks", str(framework_counts["anchor"]))
    table.add_row("Pinocchio code blocks", str(framework_counts["pinocchio"]))
    table.add_row("Native code blocks", str(framework_counts["native"]))

    console.print()
    console.print(table)


if __name__ == "__main__":
    app()
