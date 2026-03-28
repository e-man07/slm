#!/usr/bin/env python3
"""Stage 4: Prepare final training data in CPT and SFT formats.

Converts filtered JSONL into:
- CPT format: {"text": "..."} for continued pretraining
- SFT format: {"messages": [...]} ChatML for instruction tuning

Also applies Anchor 0.30+ upweighting (2-3x).

Usage:
    python scripts/prepare.py
    python scripts/prepare.py --upweight 3    # 3x modern Anchor upweighting
    python scripts/prepare.py --stats-only    # just print dataset stats
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from schema import Record, read_jsonl, today_str

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
FINAL_DIR = PROJECT_ROOT / "data" / "final"


def record_to_cpt(record: Record) -> dict:
    """Convert a record to CPT format (raw text for continued pretraining)."""
    # Add source context as a natural prefix
    prefix_parts = []
    if record.language == "rust":
        prefix_parts.append(f"// Source: {record.source}")
        if record.metadata.get("file_path"):
            prefix_parts.append(f"// File: {record.metadata['file_path']}")
        if record.metadata.get("anchor_version"):
            prefix_parts.append(f"// Anchor version: {record.metadata['anchor_version']}")
    elif record.language == "md":
        prefix_parts.append(f"<!-- Source: {record.source} -->")

    if prefix_parts:
        text = "\n".join(prefix_parts) + "\n\n" + record.content
    else:
        text = record.content

    return {"text": text}


def record_to_sft(record: Record) -> dict | None:
    """Convert a record to SFT ChatML format.

    Only works for QA-type records or code with clear structure.
    Returns None if conversion isn't meaningful.
    """
    if record.source_type == "qa":
        # Try to parse existing conversation format
        try:
            messages = json.loads(record.content)
            if isinstance(messages, list) and all(
                isinstance(m, dict) and "role" in m for m in messages
            ):
                # Already in messages format, add system prompt if missing
                if not messages or messages[0].get("role") != "system":
                    messages.insert(
                        0,
                        {
                            "role": "system",
                            "content": "You are an expert Solana and Anchor developer. Provide accurate, secure, and up-to-date code and guidance.",
                        },
                    )
                return {"messages": messages}
        except (json.JSONDecodeError, TypeError):
            pass

        # Alpaca-style: split instruction/output
        parts = record.content.split("\n\n", 2)
        if len(parts) >= 2:
            return {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert Solana and Anchor developer. Provide accurate, secure, and up-to-date code and guidance.",
                    },
                    {"role": "user", "content": parts[0].strip()},
                    {"role": "assistant", "content": "\n\n".join(parts[1:]).strip()},
                ]
            }

    if record.source_type == "code" and record.language == "rust":
        # Code → "explain this code" SFT pair
        file_path = record.metadata.get("file_path", "unknown")
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Solana and Anchor developer. Provide accurate, secure, and up-to-date code and guidance.",
                },
                {
                    "role": "user",
                    "content": f"Explain this Solana program code from `{file_path}`:\n\n```rust\n{record.content}\n```",
                },
                {
                    "role": "assistant",
                    "content": f"This is a Solana program file at `{file_path}`. Let me explain the key components:\n\n[This would be filled by synthetic generation - see scripts/synthetic.py]",
                },
            ]
        }

    return None


def write_jsonl_dicts(data: list[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for d in data:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    return len(data)


@app.command()
def prepare(
    upweight: int = typer.Option(2, help="Upweight factor for modern Anchor 0.30+ code"),
    stats_only: bool = typer.Option(False, help="Only print dataset stats, don't generate"),
    input_dir: Path = typer.Option(FINAL_DIR, help="Input directory with filtered.jsonl"),
    seed: int = typer.Option(42, help="Random seed for shuffling"),
):
    """Prepare CPT and SFT training data from filtered records."""
    input_path = Path(input_dir) / "filtered.jsonl"
    if not input_path.exists():
        console.print(f"[red]Not found: {input_path}[/red]")
        console.print("Run the filter stage first: python scripts/filter.py")
        raise typer.Exit(1)

    records = read_jsonl(input_path)
    console.print(f"[bold]Loaded {len(records)} filtered records[/bold]\n")

    # Stats
    lang_counts = Counter(r.language for r in records)
    type_counts = Counter(r.source_type for r in records)
    license_counts = Counter(r.license for r in records)
    anchor_style = Counter(r.metadata.get("anchor_style", "untagged") for r in records)

    table = Table(title="Dataset Statistics")
    table.add_column("Category", style="bold")
    table.add_column("Breakdown")

    table.add_row("Languages", ", ".join(f"{k}: {v}" for k, v in lang_counts.most_common()))
    table.add_row("Types", ", ".join(f"{k}: {v}" for k, v in type_counts.most_common()))
    table.add_row("Licenses", ", ".join(f"{k}: {v}" for k, v in license_counts.most_common()))
    table.add_row(
        "Anchor style", ", ".join(f"{k}: {v}" for k, v in anchor_style.most_common())
    )
    table.add_row("Total records", str(len(records)))
    console.print(table)

    if stats_only:
        raise typer.Exit()

    # Separate training-permitted records
    training_records = [
        r for r in records if r.metadata.get("training_permitted", "true") != "false"
    ]
    rag_only = len(records) - len(training_records)
    if rag_only > 0:
        console.print(f"\n[yellow]{rag_only} records marked RAG-only (excluded from training)[/yellow]")

    # Apply Anchor 0.30+ upweighting
    upweighted: list[Record] = []
    upweight_count = 0
    for r in training_records:
        upweighted.append(r)
        if r.metadata.get("anchor_style") == "modern" and upweight > 1:
            for _ in range(upweight - 1):
                upweighted.append(r)
            upweight_count += 1

    console.print(f"\n[bold]Upweighting:[/bold] {upweight_count} modern Anchor records × {upweight}")
    console.print(f"After upweighting: {len(upweighted)} records")

    # Shuffle
    random.seed(seed)
    random.shuffle(upweighted)

    # Generate CPT format
    console.print("\n[bold]Generating CPT format...[/bold]")
    cpt_data = [record_to_cpt(r) for r in upweighted]
    cpt_path = FINAL_DIR / "cpt_train.jsonl"
    cpt_count = write_jsonl_dicts(cpt_data, cpt_path)
    console.print(f"  [green]✓ {cpt_count} records → {cpt_path.name}[/green]")

    # Generate SFT format (only from convertible records)
    console.print("\n[bold]Generating SFT format...[/bold]")
    sft_data = []
    for r in upweighted:
        converted = record_to_sft(r)
        if converted:
            sft_data.append(converted)

    sft_path = FINAL_DIR / "sft_train.jsonl"
    sft_count = write_jsonl_dicts(sft_data, sft_path)
    console.print(f"  [green]✓ {sft_count} records → {sft_path.name}[/green]")

    # Write version metadata
    version_info = {
        "version": "slm-data-v0.1.0",
        "created_at": today_str(),
        "total_records": len(records),
        "training_records": len(training_records),
        "rag_only_records": rag_only,
        "cpt_records": cpt_count,
        "sft_records": sft_count,
        "upweight_factor": upweight,
        "upweighted_modern_anchor": upweight_count,
        "language_breakdown": dict(lang_counts),
        "type_breakdown": dict(type_counts),
        "license_breakdown": dict(license_counts),
        "anchor_style_breakdown": dict(anchor_style),
    }
    meta_path = FINAL_DIR / "dataset_meta.json"
    with open(meta_path, "w") as f:
        json.dump(version_info, f, indent=2)
    console.print(f"\n[green]✓ Metadata → {meta_path.name}[/green]")

    console.print(f"\n[bold green]Preparation complete![/bold green]")
    console.print(f"  CPT: {cpt_path} ({cpt_count} records)")
    console.print(f"  SFT: {sft_path} ({sft_count} records)")
    console.print(f"  Meta: {meta_path}")


if __name__ == "__main__":
    app()
