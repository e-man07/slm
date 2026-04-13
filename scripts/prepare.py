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

SYSTEM_PROMPT = (
    "You are an expert Solana and Anchor developer. "
    "Provide accurate, secure, and up-to-date code and guidance."
)

# Licenses that explicitly prohibit training
EXCLUDED_LICENSES = {"CC-BY-SA-4.0-no-training", "CC-BY-SA-4.0-anti-LLM"}


def _try_parse_qa_json(content: str) -> dict | None:
    """Try to parse content as a JSON Q&A object ({question, answer, ...}).
    Returns the parsed dict or None."""
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "question" in parsed and "answer" in parsed:
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _try_parse_messages_json(content: str) -> list | None:
    """Try to parse content as a ChatML messages list ([{role, content}, ...]).
    Returns the parsed list or None."""
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list) and all(
            isinstance(m, dict) and "role" in m for m in parsed
        ):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def record_to_cpt(record: Record) -> dict:
    """Convert a record to CPT format (clean text for continued pretraining).

    For Q&A records stored as JSON, extracts question + answer as natural text.
    For code records, adds source context as a comment prefix.
    """
    content = record.content

    # Handle Q&A records: flatten JSON {question, answer} into readable text
    if record.source_type == "qa":
        qa = _try_parse_qa_json(content)
        if qa:
            q = qa["question"].strip()
            a = qa["answer"].strip()
            content = f"Question: {q}\n\nAnswer: {a}"
        else:
            # Try ChatML messages list
            msgs = _try_parse_messages_json(content)
            if msgs:
                parts = []
                for m in msgs:
                    role = m.get("role", "")
                    text = m.get("content", "")
                    if role == "system":
                        continue  # Skip system prompt for CPT
                    elif role == "user":
                        parts.append(f"Question: {text}")
                    elif role == "assistant":
                        parts.append(f"Answer: {text}")
                content = "\n\n".join(parts) if parts else content

    # Add source prefix for code records
    if record.language == "rust":
        prefix = f"// Source: {record.source}"
        if record.metadata.get("file_path"):
            prefix += f"\n// File: {record.metadata['file_path']}"
        if record.metadata.get("anchor_version"):
            prefix += f"\n// Anchor version: {record.metadata['anchor_version']}"
        content = prefix + "\n\n" + content

    return {"text": content}


def record_to_sft(record: Record) -> dict | None:
    """Convert a record to SFT ChatML format.

    Handles: ChatML messages, JSON Q&A {question, answer}, Alpaca-style.
    Returns None if conversion isn't meaningful.
    """
    if record.source_type == "qa":
        # Try ChatML messages list
        msgs = _try_parse_messages_json(record.content)
        if msgs:
            if not msgs or msgs[0].get("role") != "system":
                msgs.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
            return {"messages": msgs}

        # Try JSON Q&A {question, answer}
        qa = _try_parse_qa_json(record.content)
        if qa:
            q = qa["question"].strip()
            a = qa["answer"].strip()
            if len(a) < 20:
                return None  # Skip if answer is too short
            return {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a},
                ]
            }

        # Alpaca-style: split instruction/output
        parts = record.content.split("\n\n", 2)
        if len(parts) >= 2:
            return {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": parts[0].strip()},
                    {"role": "assistant", "content": "\n\n".join(parts[1:]).strip()},
                ]
            }

    # Plain code records belong in CPT only.
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

    # Separate training-permitted records (robust boolean check + license exclusion)
    training_records = [
        r for r in records
        if str(r.metadata.get("training_permitted", "true")).lower() not in ("false", "no", "0", "pending")
        and r.license not in EXCLUDED_LICENSES
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
