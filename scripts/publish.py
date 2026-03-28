#!/usr/bin/env python3
"""Stage 4b: Publish versioned dataset to HuggingFace Hub.

Usage:
    python scripts/publish.py --repo-id your-org/slm-data --version v0.1.0
    python scripts/publish.py --repo-id your-org/slm-data --dry-run
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
FINAL_DIR = PROJECT_ROOT / "data" / "final"

DATASET_CARD_TEMPLATE = """---
license: apache-2.0
task_categories:
  - text-generation
  - question-answering
language:
  - en
tags:
  - solana
  - anchor
  - blockchain
  - code
  - rust
size_categories:
  - {size_category}
---

# SLM Training Data {version}

Training data for the Solana Language Model (SLM) — a Solana/Anchor-specialized coding LLM.

## Dataset Description

This dataset contains curated Solana/Anchor development data for fine-tuning coding LLMs.
It includes code from official repositories, documentation, Q&A pairs, and synthetic examples.

## Files

- `cpt_train.jsonl` — Continued pretraining data (`{{"text": "..."}}` format)
- `sft_train.jsonl` — Supervised fine-tuning data (ChatML `{{"messages": [...]}}` format)
- `filtered.jsonl` — Full filtered dataset in pipeline JSONL format
- `dataset_meta.json` — Version metadata and statistics

## Statistics

{stats_block}

## Data Sources

All training data is from sources with verified licenses permitting LLM training:

- Apache 2.0 repositories: Anchor, SPL, Agave, program-examples, developer-content, solana-cookbook
- Synthetic data generated via OpenAI/Anthropic APIs
- Hand-curated migration examples (old → new Anchor patterns)

**Excluded from training** (RAG-only): Stack Exchange (anti-LLM license), Helius/Metaplex docs (pending permission)

## License

Apache 2.0 — see individual record `license` fields for per-source licensing.

## Version History

- `{version}` ({date}) — Initial release
"""


@app.command()
def publish(
    repo_id: str = typer.Option(..., help="HuggingFace repo ID (e.g., your-org/slm-data)"),
    version: str = typer.Option("v0.1.0", help="Dataset version tag"),
    private: bool = typer.Option(False, help="Create as private repository"),
    dry_run: bool = typer.Option(False, help="Show what would be uploaded without uploading"),
):
    """Publish the prepared dataset to HuggingFace Hub."""
    meta_path = FINAL_DIR / "dataset_meta.json"
    if not meta_path.exists():
        console.print("[red]No dataset_meta.json found. Run prepare stage first.[/red]")
        raise typer.Exit(1)

    with open(meta_path) as f:
        meta = json.load(f)

    # Build stats block for dataset card
    total = meta.get("total_records", 0)
    stats_lines = [
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total records | {total} |",
        f"| CPT records | {meta.get('cpt_records', 0)} |",
        f"| SFT records | {meta.get('sft_records', 0)} |",
        f"| RAG-only records | {meta.get('rag_only_records', 0)} |",
        f"| Upweight factor | {meta.get('upweight_factor', 2)}x (modern Anchor) |",
    ]

    for key in ("language_breakdown", "type_breakdown", "anchor_style_breakdown"):
        breakdown = meta.get(key, {})
        if breakdown:
            label = key.replace("_breakdown", "").replace("_", " ").title()
            vals = ", ".join(f"{k}: {v}" for k, v in breakdown.items())
            stats_lines.append(f"| {label} | {vals} |")

    stats_block = "\n".join(stats_lines)

    size_cat = "1K<n<10K" if total < 10000 else "10K<n<100K" if total < 100000 else "100K<n<1M"

    card_content = DATASET_CARD_TEMPLATE.format(
        version=version,
        date=meta.get("created_at", "unknown"),
        stats_block=stats_block,
        size_category=size_cat,
    )

    # Files to upload
    files_to_upload = [
        FINAL_DIR / "cpt_train.jsonl",
        FINAL_DIR / "sft_train.jsonl",
        FINAL_DIR / "filtered.jsonl",
        FINAL_DIR / "dataset_meta.json",
    ]

    existing = [f for f in files_to_upload if f.exists()]
    missing = [f for f in files_to_upload if not f.exists()]

    console.print(f"[bold]Dataset: {repo_id} ({version})[/bold]")
    console.print(f"  Files to upload: {len(existing)}")
    for f in existing:
        size_mb = f.stat().st_size / 1024 / 1024
        console.print(f"    ✓ {f.name} ({size_mb:.1f} MB)")
    for f in missing:
        console.print(f"    ✗ {f.name} (missing)")

    if dry_run:
        console.print(f"\n[yellow]Dry run — nothing uploaded[/yellow]")
        console.print(f"\nDataset card preview:\n")
        console.print(card_content[:500] + "...")
        raise typer.Exit()

    # Upload to HuggingFace
    try:
        from huggingface_hub import HfApi
    except ImportError:
        console.print("[red]Install huggingface-hub: pip install huggingface_hub[/red]")
        raise typer.Exit(1)

    api = HfApi()

    # Create repo if needed
    console.print(f"\n[bold]Creating/updating repo: {repo_id}[/bold]")
    api.create_repo(repo_id, repo_type="dataset", private=private, exist_ok=True)

    # Upload README
    api.upload_file(
        path_or_fileobj=card_content.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"Update dataset card for {version}",
    )

    # Upload data files
    for f in existing:
        console.print(f"  Uploading {f.name}...")
        api.upload_file(
            path_or_fileobj=str(f),
            path_in_repo=f.name,
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"Add {f.name} ({version})",
        )

    # Tag the version
    api.create_tag(repo_id=repo_id, tag=version, repo_type="dataset")

    console.print(f"\n[bold green]✓ Published {repo_id} ({version})[/bold green]")
    console.print(f"  https://huggingface.co/datasets/{repo_id}")


if __name__ == "__main__":
    app()
