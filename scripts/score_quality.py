#!/usr/bin/env python3
"""Quality scoring system for SFT training records.

Assigns a quality score (0-100) to each ChatML SFT record across five
dimensions: anchor correctness, code completeness, instruction quality,
response quality, and security patterns.  Outputs scored records, a
high-quality subset, and aggregate statistics.

Usage:
    python scripts/score_quality.py
    python scripts/score_quality.py --input data/validated/sft_compilable.jsonl
    python scripts/score_quality.py --threshold 70
    python scripts/score_quality.py --stats-only
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from schema import detect_framework, is_modern_anchor, is_pinocchio

app = typer.Typer(help="Score SFT records by quality (0-100).")
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "final" / "sft_train.jsonl"
FINAL_DIR = PROJECT_ROOT / "data" / "final"

# ---------------------------------------------------------------------------
# Marker lists
# ---------------------------------------------------------------------------

MODERN_MARKERS = [
    "InitSpace",
    "ctx.bumps",
    "declare_program!",
    "solana-foundation/anchor",
    "#[program]",
    "#[derive(Accounts)]",
    "anchor_lang::prelude",
    "require!",
]

DEPRECATED_MARKERS = [
    "declare_id!",
    "coral-xyz/anchor",
    "project-serum/anchor",
    "#[state]",
]

ADVERSARIAL_FAIL_PATTERNS = [
    "ReentrancyGuard",
    "reentrancy_guard",
    "is_locked",
    "f32",
    "f64",
    "load_instruction_at",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_code(text: str) -> str:
    """Extract all code from fenced blocks, or return raw text if none."""
    blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    if blocks:
        return "\n".join(blocks)
    return text


def _get_assistant_content(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "assistant":
            return m.get("content", "")
    return ""


def _get_user_content(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "user":
            return m.get("content", "")
    return ""


def _combined_content(messages: list[dict]) -> str:
    return " ".join(m.get("content", "") for m in messages)


# ---------------------------------------------------------------------------
# Scoring dimensions
# ---------------------------------------------------------------------------


def score_anchor_correctness(code: str) -> tuple[int, list[str]]:
    """Anchor version correctness (0-20)."""
    flags: list[str] = []

    modern_hits = sum(1 for m in MODERN_MARKERS if m in code)
    has_deprecated = any(m in code for m in DEPRECATED_MARKERS)
    has_adversarial = any(p in code for p in ADVERSARIAL_FAIL_PATTERNS)

    # Base score
    if modern_hits >= 2 and not has_deprecated:
        score = 20
    elif modern_hits >= 1 and not has_deprecated:
        score = 15
    elif not any(m in code for m in MODERN_MARKERS) and not has_deprecated:
        # Generic Rust/Solana, no framework markers
        score = 10
    elif has_deprecated and modern_hits >= 1:
        score = 5
        flags.append("mixed_anchor_versions")
    else:
        score = 0
        if has_deprecated:
            flags.append("deprecated_anchor_patterns")

    # Adversarial penalty
    if has_adversarial:
        penalty_hits = [p for p in ADVERSARIAL_FAIL_PATTERNS if p in code]
        flags.append(f"adversarial_fail:{','.join(penalty_hits)}")
        score = max(score - 10, 0)

    return score, flags


def score_code_completeness(code: str) -> tuple[int, list[str]]:
    """Code completeness (0-20)."""
    score = 0
    flags: list[str] = []

    # Has use/import statements
    if re.search(r"\buse\s+\w+", code):
        score += 5

    # Has type definitions
    if re.search(r"#\[account\]|#\[derive\(|struct\s+\w+|enum\s+\w+", code):
        score += 5

    # Has complete function bodies (no placeholders)
    incomplete_markers = ["// ...", "todo!()", "unimplemented!()", "/* ... */"]
    if any(m in code for m in incomplete_markers):
        flags.append("incomplete_code")
    else:
        score += 5

    # Has error handling
    if re.search(r"Result<\(\)>|require!|error_code|ErrorCode|err!\(|error!\(", code):
        score += 5
    else:
        flags.append("missing_error_handling")

    return score, flags


def score_instruction_quality(user_msg: str) -> tuple[int, list[str]]:
    """Instruction quality (0-20)."""
    score = 0
    flags: list[str] = []

    # Length and specificity
    if len(user_msg) > 20:
        score += 10
    elif len(user_msg) > 10:
        score += 5
    else:
        flags.append("trivially_short_instruction")

    # Includes framework/scenario context
    context_markers = [
        "anchor", "solana", "program", "token", "account", "pda",
        "spl", "nft", "stake", "swap", "vault", "mint", "cpi",
        "instruction", "transaction", "signer", "pinocchio",
    ]
    if any(m in user_msg.lower() for m in context_markers):
        score += 5
    else:
        flags.append("no_domain_context")

    # Not trivially phrased (has some detail beyond "show me X")
    trivial_prefixes = [
        "show me", "write", "give me", "create a", "make a",
        "generate", "build", "code",
    ]
    stripped = user_msg.strip().lower()
    is_trivial = any(stripped.startswith(p) for p in trivial_prefixes) and len(user_msg) < 40
    if not is_trivial:
        score += 5
    else:
        flags.append("trivial_phrasing")

    return score, flags


def score_response_quality(assistant_msg: str) -> tuple[int, list[str]]:
    """Response quality (0-20)."""
    score = 0
    flags: list[str] = []

    has_code_blocks = "```" in assistant_msg
    # Strip code blocks to get natural language portion
    nl_text = re.sub(r"```[\s\S]*?```", "", assistant_msg).strip()

    # Includes natural language explanation
    if len(nl_text) > 30:
        score += 5
    else:
        flags.append("no_explanation")

    # Has properly fenced code blocks
    if re.search(r"```rust", assistant_msg):
        score += 5
    elif has_code_blocks:
        score += 3  # partial credit for unfenced blocks
        flags.append("unfenced_code_blocks")
    else:
        flags.append("no_code_blocks")

    # Explains trade-offs, best practices, or security
    quality_markers = [
        "security", "best practice", "trade-off", "tradeoff",
        "important", "note that", "be careful", "avoid",
        "recommend", "instead", "safer", "better",
        "vulnerability", "attack", "exploit",
    ]
    if any(m in assistant_msg.lower() for m in quality_markers):
        score += 5
    else:
        flags.append("no_best_practices")

    # Response length sweet spot (200-3000 chars)
    length = len(assistant_msg)
    if 200 <= length <= 3000:
        score += 5
    elif length < 200:
        flags.append("response_too_short")
    else:
        flags.append("response_too_long")

    return score, flags


def score_security_patterns(code: str) -> tuple[int, list[str]]:
    """Security patterns (0-20)."""
    score = 0
    flags: list[str] = []
    framework = detect_framework(code)

    # Checked arithmetic
    checked_ops = ["checked_add", "checked_mul", "checked_div", "checked_sub"]
    if any(op in code for op in checked_ops):
        score += 5
    else:
        # Only flag if there's arithmetic happening
        if re.search(r"[\+\-\*\/]\s*\d|\.add\(|\.sub\(|\.mul\(|\.div\(", code):
            flags.append("missing_checked_arithmetic")

    # Signer validation
    signer_markers = ["Signer<'info>", "has_one", "constraint", "Signer<"]
    if any(m in code for m in signer_markers):
        score += 5
    else:
        flags.append("missing_signer_validation")

    # No unsafe blocks (unless Pinocchio)
    if "unsafe" in code:
        if framework == "pinocchio":
            score += 5  # expected for Pinocchio
        else:
            flags.append("unsafe_code")
    else:
        score += 5

    # PDA constraints
    has_pda = "seeds" in code or "find_program_address" in code
    if has_pda:
        if "bump" in code:
            score += 5
        else:
            flags.append("pda_missing_bump")
    else:
        # No PDAs involved — give full credit (not applicable)
        score += 5

    return score, flags


# ---------------------------------------------------------------------------
# Main scoring
# ---------------------------------------------------------------------------


def score_record(record: dict) -> dict:
    """Score a single SFT record. Returns the record with _quality added."""
    messages = record.get("messages", [])
    user_msg = _get_user_content(messages)
    assistant_msg = _get_assistant_content(messages)
    code = _extract_code(assistant_msg)
    all_flags: list[str] = []

    # Score each dimension
    anchor_score, anchor_flags = score_anchor_correctness(code)
    completeness_score, completeness_flags = score_code_completeness(code)
    instruction_score, instruction_flags = score_instruction_quality(user_msg)
    response_score, response_flags = score_response_quality(assistant_msg)
    security_score, security_flags = score_security_patterns(code)

    all_flags.extend(anchor_flags)
    all_flags.extend(completeness_flags)
    all_flags.extend(instruction_flags)
    all_flags.extend(response_flags)
    all_flags.extend(security_flags)

    total = (
        anchor_score
        + completeness_score
        + instruction_score
        + response_score
        + security_score
    )

    record["_quality"] = {
        "total": total,
        "anchor_correctness": anchor_score,
        "code_completeness": completeness_score,
        "instruction_quality": instruction_score,
        "response_quality": response_score,
        "security_patterns": security_score,
        "flags": all_flags,
    }
    return record


# ---------------------------------------------------------------------------
# Stats and reporting
# ---------------------------------------------------------------------------


def compute_stats(scored: list[dict]) -> dict:
    """Compute aggregate quality statistics."""
    if not scored:
        return {"count": 0}

    totals = [r["_quality"]["total"] for r in scored]
    dimensions = [
        "anchor_correctness",
        "code_completeness",
        "instruction_quality",
        "response_quality",
        "security_patterns",
    ]

    # Score distribution buckets
    buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    for t in totals:
        if t < 20:
            buckets["0-20"] += 1
        elif t < 40:
            buckets["20-40"] += 1
        elif t < 60:
            buckets["40-60"] += 1
        elif t < 80:
            buckets["60-80"] += 1
        else:
            buckets["80-100"] += 1

    # Per-dimension averages
    dim_avgs = {}
    for dim in dimensions:
        vals = [r["_quality"][dim] for r in scored]
        dim_avgs[dim] = round(sum(vals) / len(vals), 2)

    # Flag frequency
    flag_counts: dict[str, int] = {}
    for r in scored:
        for flag in r["_quality"]["flags"]:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    sorted_totals = sorted(totals)
    n = len(sorted_totals)

    return {
        "count": n,
        "mean": round(sum(totals) / n, 2),
        "median": sorted_totals[n // 2],
        "min": sorted_totals[0],
        "max": sorted_totals[-1],
        "p25": sorted_totals[n // 4],
        "p75": sorted_totals[3 * n // 4],
        "distribution": buckets,
        "dimension_averages": dim_avgs,
        "top_flags": dict(sorted(flag_counts.items(), key=lambda x: -x[1])[:20]),
    }


def print_stats(stats: dict) -> None:
    """Print quality statistics with rich formatting."""
    if stats["count"] == 0:
        console.print("[red]No records to report on.[/red]")
        return

    console.print(f"\n[bold]Quality Scoring Report[/bold]")
    console.print(f"  Records scored: {stats['count']}")
    console.print(
        f"  Mean: {stats['mean']}  Median: {stats['median']}  "
        f"Min: {stats['min']}  Max: {stats['max']}  "
        f"P25: {stats['p25']}  P75: {stats['p75']}"
    )

    # Distribution table
    dist_table = Table(title="Score Distribution")
    dist_table.add_column("Range", style="cyan")
    dist_table.add_column("Count", justify="right", style="green")
    dist_table.add_column("Pct", justify="right", style="yellow")

    for bucket, count in stats["distribution"].items():
        pct = count / stats["count"] * 100
        dist_table.add_row(bucket, str(count), f"{pct:.1f}%")
    console.print(dist_table)

    # Dimension averages table
    dim_table = Table(title="Per-Dimension Averages (max 20)")
    dim_table.add_column("Dimension", style="cyan")
    dim_table.add_column("Avg", justify="right", style="green")

    for dim, avg in stats["dimension_averages"].items():
        dim_table.add_row(dim, str(avg))
    console.print(dim_table)

    # Top flags
    if stats["top_flags"]:
        flag_table = Table(title="Most Common Flags")
        flag_table.add_column("Flag", style="cyan")
        flag_table.add_column("Count", justify="right", style="yellow")

        for flag, count in stats["top_flags"].items():
            flag_table.add_row(flag, str(count))
        console.print(flag_table)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.command()
def main(
    input: Path = typer.Option(
        DEFAULT_INPUT, "--input", "-i", help="Input JSONL file with ChatML SFT records"
    ),
    threshold: int = typer.Option(
        60, "--threshold", "-t", help="Minimum quality score for high-quality subset"
    ),
    output_dir: Path = typer.Option(
        FINAL_DIR, "--output-dir", "-o", help="Output directory"
    ),
    stats_only: bool = typer.Option(
        False, "--stats-only", help="Print stats without writing output files"
    ),
) -> None:
    """Score SFT training records by quality (0-100)."""
    input = Path(input)
    output_dir = Path(output_dir)

    if not input.exists():
        console.print(f"[red]Input file not found: {input}[/red]")
        raise typer.Exit(1)

    # Load records
    console.print(f"[bold]Loading records from {input}[/bold]")
    records: list[dict] = []
    with open(input, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    console.print(f"  Loaded {len(records)} records\n")

    if not records:
        console.print("[red]No records found.[/red]")
        raise typer.Exit(1)

    # Score all records
    scored: list[dict] = []
    for record in track(records, description="Scoring"):
        scored.append(score_record(record))

    # Compute and print stats
    stats = compute_stats(scored)
    print_stats(stats)

    # High-quality subset
    high_quality = [r for r in scored if r["_quality"]["total"] >= threshold]
    console.print(
        f"\n[bold]Threshold {threshold}:[/bold] "
        f"{len(high_quality)}/{len(scored)} records "
        f"({len(high_quality) / len(scored) * 100:.1f}%) qualify"
    )

    if stats_only:
        console.print("[dim]--stats-only: skipping file output[/dim]")
        return

    # Write output files
    output_dir.mkdir(parents=True, exist_ok=True)

    scored_path = output_dir / "sft_scored.jsonl"
    hq_path = output_dir / "sft_highquality.jsonl"
    report_path = output_dir / "quality_report.json"

    with open(scored_path, "w", encoding="utf-8") as f:
        for r in scored:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    console.print(f"  [green]All scored:[/green]     {len(scored):>5}  ->  {scored_path}")

    with open(hq_path, "w", encoding="utf-8") as f:
        for r in high_quality:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    console.print(f"  [green]High quality:[/green]   {len(high_quality):>5}  ->  {hq_path}")

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    console.print(f"  [green]Stats report:[/green]          ->  {report_path}")

    console.print(f"\n[bold green]Done.[/bold green]")


if __name__ == "__main__":
    app()
