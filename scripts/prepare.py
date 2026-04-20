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

from schema import Record, read_jsonl, today_str, is_pinocchio, detect_framework

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

    # Code records with pre-formatted ChatML messages (from gen_sft_from_code.py)
    if record.source_type in ("code", "synthetic"):
        msgs = _try_parse_messages_json(record.content)
        if msgs:
            if not msgs or msgs[0].get("role") != "system":
                msgs.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
            return {"messages": msgs}

    # Plain code records without ChatML belong in CPT only.
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
    console.print(f"[bold]Loaded {len(records)} filtered records[/bold]")

    # Also ingest SFT records from collected/ and validated/ directories
    collected_dir = PROJECT_ROOT / "data" / "collected"
    validated_dir = PROJECT_ROOT / "data" / "validated"
    extra_sources = []

    # Also load SFT variant files from processed/ that aren't in Record format
    processed_dir = PROJECT_ROOT / "data" / "processed"

    for extra_dir in [collected_dir, validated_dir, processed_dir]:
        if not extra_dir.exists():
            continue
        for jsonl_file in sorted(extra_dir.glob("*.jsonl")):
            # Skip DPO files (not SFT training data)
            if "dpo-" in jsonl_file.name:
                continue
            try:
                extra_records = read_jsonl(jsonl_file)
                extra_sources.append((jsonl_file.name, len(extra_records)))
                records.extend(extra_records)
            except (TypeError, KeyError):
                # File is raw ChatML format (not Record) — convert on the fly
                try:
                    chatml_count = 0
                    with open(jsonl_file, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            parsed = json.loads(line)
                            if "messages" in parsed:
                                content = json.dumps(parsed["messages"], ensure_ascii=False)
                                r = Record(
                                    id=Record.make_id(content),
                                    source=f"sft/{jsonl_file.stem}",
                                    source_type="qa",
                                    content=content,
                                    language="rust",
                                    license="Apache-2.0",
                                    metadata={
                                        "training_permitted": True,
                                        "anchor_style": "modern",
                                    },
                                )
                                records.append(r)
                                chatml_count += 1
                    if chatml_count > 0:
                        extra_sources.append((jsonl_file.name, chatml_count))
                except Exception as e2:
                    console.print(f"  [yellow]Skipped {jsonl_file.name}: {e2}[/yellow]")
            except Exception as e:
                console.print(f"  [yellow]Skipped {jsonl_file.name}: {e}[/yellow]")

    if extra_sources:
        console.print(f"[bold]Extra SFT sources ingested:[/bold]")
        for name, count in extra_sources:
            console.print(f"  {name}: {count} records")
        console.print(f"[bold]Total after merge: {len(records)} records[/bold]\n")
    else:
        console.print()

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

    # Apply multi-factor upweighting
    upweighted: list[Record] = []
    upweight_count = 0
    pinocchio_count = 0
    adversarial_count = 0
    compilable_count = 0
    for r in training_records:
        # Determine upweight multiplier (take the highest applicable)
        multiplier = 1
        framework = r.metadata.get("framework", "")
        method = r.metadata.get("method", "")
        compile_status = r.metadata.get("compile_status", "")

        if framework == "pinocchio" or is_pinocchio(r.content):
            multiplier = max(multiplier, 3)  # Pinocchio: 3x (rarest, most valuable)
            pinocchio_count += 1
        if r.metadata.get("anchor_style") == "modern" and upweight > 1:
            multiplier = max(multiplier, upweight)  # Modern Anchor: 2x default
            upweight_count += 1
        if method == "adversarial-refusal":
            multiplier = max(multiplier, 2)  # Adversarial refusals: 2x
            adversarial_count += 1
        if compile_status == "pass":
            compilable_count += 1
            # Compilable code gets a slight boost (round up)
            if multiplier == 1:
                multiplier = 2  # 1.5x → round to 2x for simplicity

        for _ in range(multiplier):
            upweighted.append(r)

    console.print(f"\n[bold]Upweighting:[/bold]")
    console.print(f"  Modern Anchor records: {upweight_count} × {upweight}")
    console.print(f"  Pinocchio records: {pinocchio_count} × 3")
    console.print(f"  Adversarial refusals: {adversarial_count} × 2")
    console.print(f"  Compilable code: {compilable_count}")
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
