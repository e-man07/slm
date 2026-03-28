#!/usr/bin/env python3
"""Concatenate DPO chosen/rejected JSONL files into single files for training.

Merges all dpo-chosen*.jsonl → dpo_chosen.jsonl
       all dpo-rejected*.jsonl → dpo_rejected.jsonl

Usage:
    python training/prepare_dpo.py
    python training/prepare_dpo.py --data-dir /workspace/data
    python training/prepare_dpo.py --data-dir /home/e-man/slm/data/processed
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer()


def collect_files(data_dir: Path, prefix: str) -> list[Path]:
    """Find all JSONL files matching prefix, checking multiple directories."""
    files = []
    for subdir in [data_dir, data_dir / "processed", data_dir / "synthetic"]:
        if subdir.is_dir():
            files.extend(sorted(subdir.glob(f"{prefix}*.jsonl")))
    return files


@app.command()
def main(
    data_dir: Path = typer.Option("/workspace/data", help="Root data directory"),
    output_dir: Path = typer.Option("/workspace/data", help="Output directory"),
    dry_run: bool = typer.Option(False, help="Just print what would be merged"),
):
    chosen_files = collect_files(data_dir, "dpo-chosen")
    rejected_files = collect_files(data_dir, "dpo-rejected")

    print(f"Found {len(chosen_files)} chosen files:")
    for f in chosen_files:
        print(f"  {f.name}")
    print(f"Found {len(rejected_files)} rejected files:")
    for f in rejected_files:
        print(f"  {f.name}")

    if dry_run:
        return

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Merge chosen
    chosen_out = output_dir / "dpo_chosen.jsonl"
    chosen_count = 0
    with open(chosen_out, "w") as out:
        for f in chosen_files:
            with open(f) as inp:
                for line in inp:
                    if line.strip():
                        out.write(line if line.endswith("\n") else line + "\n")
                        chosen_count += 1
    print(f"\n✓ {chosen_count} chosen records → {chosen_out}")

    # Merge rejected
    rejected_out = output_dir / "dpo_rejected.jsonl"
    rejected_count = 0
    with open(rejected_out, "w") as out:
        for f in rejected_files:
            with open(f) as inp:
                for line in inp:
                    if line.strip():
                        out.write(line if line.endswith("\n") else line + "\n")
                        rejected_count += 1
    print(f"✓ {rejected_count} rejected records → {rejected_out}")

    if chosen_count != rejected_count:
        print(f"\n⚠ Mismatch: {chosen_count} chosen vs {rejected_count} rejected")
        print(f"  DPO will use min({chosen_count}, {rejected_count}) pairs")
    else:
        print(f"\n✓ {chosen_count} aligned preference pairs ready for DPO")


if __name__ == "__main__":
    app()
