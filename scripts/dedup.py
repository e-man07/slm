#!/usr/bin/env python3
"""Stage 2: Deduplicate collected data.

Three-layer dedup:
1. Exact dedup via SHA-256 (already the record ID)
2. Near-dedup via MinHash LSH (128 perms, 3-shingles, 0.8 threshold)
3. Priority ordering for conflict resolution

Usage:
    python scripts/dedup.py
    python scripts/dedup.py --threshold 0.7   # lower threshold = more aggressive
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import typer
from datasketch import MinHash, MinHashLSH
from rich.console import Console
from rich.progress import track

from schema import Record, normalize_for_hashing, read_jsonl, write_jsonl

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEDUPED_DIR = PROJECT_ROOT / "data" / "deduped"

# Priority ordering: higher = keep over lower
SOURCE_PRIORITY = {
    "hand-curated": 100,
    "github/solana-foundation": 80,
    "github/solana-developers": 80,
    "github/solana-labs": 75,
    "github/anza-xyz": 75,
    "huggingface/lumolabs-ai": 50,
    "crawl/": 30,
    "synthetic/": 20,
}

NUM_PERMS = 128
NUM_SHINGLES = 3


def get_priority(source: str) -> int:
    """Get priority score for a source. Higher = preferred."""
    for prefix, priority in SOURCE_PRIORITY.items():
        if source.startswith(prefix) or prefix in source:
            return priority
    return 10  # default low priority


def make_shingles(text: str, n: int = NUM_SHINGLES) -> set[str]:
    """Create word-level n-shingles from text."""
    words = text.split()
    if len(words) < n:
        return {text}
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def compute_minhash(text: str) -> MinHash:
    """Compute MinHash signature for text."""
    m = MinHash(num_perm=NUM_PERMS)
    for shingle in make_shingles(text):
        m.update(shingle.encode("utf-8"))
    return m


@app.command()
def dedup(
    threshold: float = typer.Option(0.8, help="Jaccard similarity threshold for near-dedup"),
    input_dir: Path = typer.Option(PROCESSED_DIR, help="Input directory with JSONL files"),
    output_dir: Path = typer.Option(DEDUPED_DIR, help="Output directory for deduped JSONL"),
):
    """Run three-layer deduplication on processed data."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load all records from all JSONL files
    console.print("[bold]Loading records...[/bold]")
    all_records: list[Record] = []
    jsonl_files = sorted(input_dir.glob("*.jsonl"))

    if not jsonl_files:
        console.print(f"[red]No JSONL files found in {input_dir}[/red]")
        raise typer.Exit(1)

    skipped_files: list[str] = []
    for f in jsonl_files:
        try:
            records = read_jsonl(f)
            console.print(f"  {f.name}: {len(records)} records")
            all_records.extend(records)
        except (TypeError, KeyError) as exc:
            # Skip files that aren't in Record format (e.g., raw ChatML SFT variants)
            # These will be ingested directly by prepare.py from collected/validated dirs
            skipped_files.append(f.name)
            console.print(f"  [dim]{f.name}: skipped (not Record format)[/dim]")

    if skipped_files:
        console.print(f"\n[yellow]Skipped {len(skipped_files)} non-Record files (handled by prepare.py)[/yellow]")

    total_before = len(all_records)
    console.print(f"\n[bold]Total records: {total_before}[/bold]")

    # Stage 1: Exact dedup via SHA-256 on normalized content
    # (strip whitespace/comments for code before hashing, per research doc)
    console.print("\n[bold]Stage 1: Exact dedup (SHA-256 on normalized content)...[/bold]")
    seen_hashes: dict[str, Record] = {}
    exact_dupes = 0

    for r in all_records:
        # Normalize before hashing so formatting-only differences are caught
        normalized = normalize_for_hashing(r.content, r.language)
        norm_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        if norm_hash in seen_hashes:
            exact_dupes += 1
            existing = seen_hashes[norm_hash]
            # Keep higher-priority version
            if get_priority(r.source) > get_priority(existing.source):
                seen_hashes[norm_hash] = r
        else:
            seen_hashes[norm_hash] = r

    after_exact = list(seen_hashes.values())
    console.print(f"  Removed {exact_dupes} exact duplicates ({len(after_exact)} remaining)")

    # Stage 2: Near-dedup via MinHash LSH
    console.print(f"\n[bold]Stage 2: Near-dedup (MinHash LSH, threshold={threshold})...[/bold]")
    lsh = MinHashLSH(threshold=threshold, num_perm=NUM_PERMS)

    # Sort by priority (highest first) so higher-priority records get inserted first
    after_exact.sort(key=lambda r: get_priority(r.source), reverse=True)

    kept: list[Record] = []
    near_dupes = 0

    for record in track(after_exact, description="  Computing MinHash LSH"):
        # Normalize content before hashing
        normalized = normalize_for_hashing(record.content, record.language)
        if not normalized:
            continue

        mh = compute_minhash(normalized)

        # Check for near-duplicates
        try:
            result = lsh.query(mh)
        except ValueError:
            result = []

        if result:
            near_dupes += 1
            continue  # Skip — a similar record with higher/equal priority already exists

        # Insert into LSH and keep
        try:
            lsh.insert(record.id, mh)
            kept.append(record)
        except ValueError:
            # Duplicate key in LSH (shouldn't happen after exact dedup, but be safe)
            near_dupes += 1

    console.print(f"  Removed {near_dupes} near-duplicates ({len(kept)} remaining)")

    # Write output
    out_path = output_dir / "deduped.jsonl"
    count = write_jsonl(kept, out_path)

    # Stats
    total_removed = total_before - count
    reduction_pct = (total_removed / total_before * 100) if total_before > 0 else 0

    console.print(f"\n[bold green]Deduplication complete:[/bold green]")
    console.print(f"  Before:    {total_before}")
    console.print(f"  After:     {count}")
    console.print(f"  Removed:   {total_removed} ({reduction_pct:.1f}%)")
    console.print(f"  Output:    {out_path}")

    # Source breakdown
    console.print(f"\n[bold]Records by source:[/bold]")
    source_counts: dict[str, int] = {}
    for r in kept:
        # Group by top-level source
        key = r.source.split("/")[0] + "/" + r.source.split("/")[1] if "/" in r.source else r.source
        source_counts[key] = source_counts.get(key, 0) + 1
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        console.print(f"  {source}: {count}")


if __name__ == "__main__":
    app()
