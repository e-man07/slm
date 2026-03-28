#!/usr/bin/env python3
"""Filter docs/crawl content by KenLM perplexity score.

Removes records above the 95th percentile perplexity (likely low-quality,
boilerplate, or garbled text). Only applies to docs/crawl content —
code and synthetic data are excluded.

Requires: pip install kenlm
Also requires a pre-trained KenLM language model (.arpa or .bin).

Usage:
    # First, train a KenLM model on the docs corpus:
    python scripts/filter_perplexity.py --train

    # Then filter:
    python scripts/filter_perplexity.py --filter

    # Or do both:
    python scripts/filter_perplexity.py --train --filter
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "data" / "models"
LM_PATH = MODEL_DIR / "docs_lm.arpa"
LM_BIN_PATH = MODEL_DIR / "docs_lm.bin"

# Only filter these source types (docs/crawl content)
FILTERABLE_TYPES = {"docs"}
# Only filter these file prefixes
FILTERABLE_PREFIXES = ("crawl-",)

PERCENTILE_CUTOFF = 95  # Remove above this percentile


def get_docs_records() -> list[tuple[Path, int, dict]]:
    """Collect all docs/crawl records with their file paths and line numbers."""
    records = []
    for path in sorted(PROCESSED_DIR.glob("*.jsonl")):
        if not any(path.name.startswith(p) for p in FILTERABLE_PREFIXES):
            continue
        with open(path) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("source_type") in FILTERABLE_TYPES:
                    records.append((path, i, rec))
    return records


def extract_text_corpus(records: list[tuple[Path, int, dict]]) -> str:
    """Extract text content for LM training."""
    lines = []
    for _, _, rec in records:
        content = rec.get("content", "")
        # Normalize: one sentence per line (rough split)
        for sent in content.replace("\n", " ").split(". "):
            sent = sent.strip()
            if len(sent) > 20:
                lines.append(sent)
    return "\n".join(lines)


def train_lm(text_corpus: str, order: int = 3):
    """Train a KenLM language model on the text corpus."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Write corpus to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(text_corpus)
        corpus_path = f.name

    try:
        # Find lmplz binary
        lmplz = "lmplz"
        # Try to find it
        result = subprocess.run(["which", lmplz], capture_output=True, text=True)
        if result.returncode != 0:
            # Try common locations
            for candidate in [
                "/usr/local/bin/lmplz",
                "/usr/bin/lmplz",
                os.path.expanduser("~/.local/bin/lmplz"),
            ]:
                if os.path.exists(candidate):
                    lmplz = candidate
                    break
            else:
                console.print("[red]lmplz not found. Install KenLM:[/red]")
                console.print("  sudo apt-get install libboost-all-dev cmake")
                console.print("  pip install kenlm")
                console.print("  # Or build from source: https://github.com/kpu/kenlm")
                raise typer.Exit(1)

        console.print(f"  Training {order}-gram LM on {len(text_corpus):,} chars...")
        with open(str(LM_PATH), "w") as out_f:
            subprocess.run(
                [lmplz, "-o", str(order), "--discount_fallback"],
                stdin=open(corpus_path),
                stdout=out_f,
                stderr=subprocess.PIPE,
                check=True,
            )
        console.print(f"  [green]✓ LM saved to {LM_PATH}[/green]")
    finally:
        os.unlink(corpus_path)


def score_records(records: list[tuple[Path, int, dict]]) -> list[float]:
    """Score each record's perplexity using KenLM."""
    import kenlm

    model_path = str(LM_BIN_PATH) if LM_BIN_PATH.exists() else str(LM_PATH)
    if not os.path.exists(model_path):
        console.print(f"[red]No LM found at {model_path}. Run with --train first.[/red]")
        raise typer.Exit(1)

    model = kenlm.Model(model_path)
    scores = []
    for _, _, rec in records:
        content = rec.get("content", "")
        # Score per-sentence, average
        sentences = [s.strip() for s in content.replace("\n", " ").split(". ") if len(s.strip()) > 10]
        if not sentences:
            scores.append(float("inf"))
            continue
        sent_scores = []
        for sent in sentences:
            # KenLM returns log10 probability; convert to perplexity
            log_prob = model.score(sent)
            words = len(sent.split())
            if words > 0:
                perplexity = 10 ** (-log_prob / words)
                sent_scores.append(perplexity)
        scores.append(sum(sent_scores) / len(sent_scores) if sent_scores else float("inf"))
    return scores


@app.command()
def main(
    train: bool = typer.Option(False, help="Train KenLM language model"),
    filter: bool = typer.Option(False, "--filter", help="Filter by perplexity"),
    cutoff: int = typer.Option(PERCENTILE_CUTOFF, help="Percentile cutoff"),
    dry_run: bool = typer.Option(False, help="Show what would be removed without modifying files"),
):
    """Filter docs content by KenLM perplexity."""
    records = get_docs_records()
    console.print(f"Found {len(records)} docs/crawl records across processed files")

    if not records:
        console.print("[yellow]No filterable records found[/yellow]")
        raise typer.Exit()

    if train:
        console.print("\n[bold blue]Training KenLM language model...[/bold blue]")
        corpus = extract_text_corpus(records)
        train_lm(corpus)

    if filter:
        console.print(f"\n[bold blue]Scoring records (cutoff: {cutoff}th percentile)...[/bold blue]")
        scores = score_records(records)

        # Calculate percentile threshold
        valid_scores = sorted([s for s in scores if s != float("inf")])
        if not valid_scores:
            console.print("[yellow]No valid scores[/yellow]")
            raise typer.Exit()

        idx = int(len(valid_scores) * cutoff / 100)
        threshold = valid_scores[min(idx, len(valid_scores) - 1)]
        console.print(f"  Perplexity threshold (p{cutoff}): {threshold:.1f}")
        console.print(f"  Median perplexity: {valid_scores[len(valid_scores)//2]:.1f}")
        console.print(f"  Min: {valid_scores[0]:.1f}, Max: {valid_scores[-1]:.1f}")

        # Group removals by file
        removals_by_file: dict[Path, set[int]] = {}
        removed = 0
        for (path, line_idx, rec), score in zip(records, scores):
            if score > threshold:
                if path not in removals_by_file:
                    removals_by_file[path] = set()
                removals_by_file[path].add(line_idx)
                removed += 1

        console.print(f"  Records to remove: {removed}/{len(records)} ({removed/len(records)*100:.1f}%)")

        if dry_run:
            console.print("[yellow]Dry run — no files modified[/yellow]")
            for path, indices in removals_by_file.items():
                console.print(f"  Would remove {len(indices)} records from {path.name}")
            raise typer.Exit()

        # Rewrite files without removed records
        for path, indices in removals_by_file.items():
            lines = path.read_text().strip().split("\n")
            new_lines = [l for i, l in enumerate(lines) if i not in indices]
            path.write_text("\n".join(new_lines) + "\n" if new_lines else "")
            console.print(f"  {path.name}: removed {len(indices)}, kept {len(new_lines)}")

        console.print(f"\n[bold green]Done. Removed {removed} low-quality records.[/bold green]")

    if not train and not filter:
        console.print("[yellow]Specify --train and/or --filter[/yellow]")


if __name__ == "__main__":
    app()
